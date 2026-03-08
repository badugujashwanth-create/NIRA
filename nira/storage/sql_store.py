from __future__ import annotations

import json
import logging
import threading
from datetime import datetime, timezone
from dataclasses import dataclass
from typing import Any


logger = logging.getLogger(__name__)


@dataclass
class DBConfig:
    host: str
    port: int
    user: str
    password: str
    database: str


class SQLStore:
    def __init__(self, config: DBConfig, enabled: bool = True) -> None:
        self.config = config
        self.enabled = enabled
        self.available = False
        self._lock = threading.Lock()
        self._mysql_connector = None
        self._pooling = None
        self._pool = None
        if enabled:
            self._initialize()

    def _initialize(self) -> None:
        try:
            import mysql.connector  # type: ignore
            from mysql.connector import pooling  # type: ignore

            self._mysql_connector = mysql.connector
            self._pooling = pooling
        except Exception as exc:
            logger.error("mysql-connector-python is not available: %s", exc)
            self.available = False
            return

        try:
            self._ensure_database()
            self._create_pool()
            self._ensure_schema()
            self.available = True
            logger.info(
                "SQL storage connected to %s:%s/%s",
                self.config.host,
                self.config.port,
                self.config.database,
            )
        except Exception as exc:
            logger.error("Failed to initialize SQL storage: %s", exc)
            self.available = False

    def _create_pool(self) -> None:
        if not self._pooling:
            raise RuntimeError("MySQL pooling module unavailable.")
        self._pool = self._pooling.MySQLConnectionPool(
            pool_name="nira_agent_pool",
            pool_size=8,
            host=self.config.host,
            port=self.config.port,
            user=self.config.user,
            password=self.config.password,
            database=self.config.database,
            autocommit=True,
            connection_timeout=8,
        )

    def _connect(self, include_db: bool = True):
        if include_db and self._pool is not None:
            return self._pool.get_connection()
        if not self._mysql_connector:
            raise RuntimeError("MySQL client unavailable.")
        kwargs = {
            "host": self.config.host,
            "port": self.config.port,
            "user": self.config.user,
            "password": self.config.password,
            "autocommit": True,
            "connection_timeout": 8,
        }
        if include_db:
            kwargs["database"] = self.config.database
        return self._mysql_connector.connect(**kwargs)

    def _ensure_database(self) -> None:
        with self._connect(include_db=False) as conn:
            with conn.cursor() as cur:
                cur.execute(f"CREATE DATABASE IF NOT EXISTS `{self.config.database}`")

    def _ensure_schema(self) -> None:
        with self._connect(include_db=True) as conn:
            with conn.cursor() as cur:
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS preferences (
                        pref_key VARCHAR(191) PRIMARY KEY,
                        pref_value LONGTEXT NOT NULL,
                        updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
                    )
                    """
                )
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS long_term_memory (
                        id BIGINT AUTO_INCREMENT PRIMARY KEY,
                        ts VARCHAR(64) NOT NULL,
                        kind VARCHAR(64) NOT NULL,
                        content_enc LONGTEXT NOT NULL
                    )
                    """
                )
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS audit_logs (
                        id BIGINT AUTO_INCREMENT PRIMARY KEY,
                        ts VARCHAR(64) NOT NULL,
                        event_name VARCHAR(128) NOT NULL,
                        payload_enc LONGTEXT NOT NULL
                    )
                    """
                )
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS simulation_logs (
                        id BIGINT AUTO_INCREMENT PRIMARY KEY,
                        ts VARCHAR(64) NOT NULL,
                        command_name VARCHAR(128) NOT NULL,
                        risk_level VARCHAR(32) NOT NULL,
                        payload_json LONGTEXT NOT NULL
                    )
                    """
                )
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS syscall_profiles (
                        id BIGINT AUTO_INCREMENT PRIMARY KEY,
                        ts VARCHAR(64) NOT NULL,
                        command_name VARCHAR(128) NOT NULL,
                        duration_ms DOUBLE NOT NULL,
                        syscall_intensity VARCHAR(32) NOT NULL,
                        kernel_transition_cost VARCHAR(32) NOT NULL,
                        subsystems_json LONGTEXT NOT NULL,
                        success TINYINT(1) NOT NULL
                    )
                    """
                )
                cur.execute(
                    """
                    CREATE TABLE IF NOT EXISTS repair_attempts (
                        id BIGINT AUTO_INCREMENT PRIMARY KEY,
                        ts VARCHAR(64) NOT NULL,
                        command_name VARCHAR(128) NOT NULL,
                        attempt_no INT NOT NULL,
                        error_text LONGTEXT NOT NULL,
                        success TINYINT(1) NOT NULL
                    )
                    """
                )

    def set_preference(self, key: str, value: Any) -> bool:
        if not self.available:
            return False
        payload = json.dumps(value, ensure_ascii=False)
        with self._lock:
            try:
                with self._connect(include_db=True) as conn:
                    with conn.cursor() as cur:
                        cur.execute(
                            """
                            INSERT INTO preferences (pref_key, pref_value)
                            VALUES (%s, %s)
                            ON DUPLICATE KEY UPDATE pref_value = VALUES(pref_value)
                            """,
                            (key, payload),
                        )
                return True
            except Exception as exc:
                logger.error("set_preference failed for key=%s: %s", key, exc)
                return False

    def get_preference(self, key: str, default: Any = None) -> Any:
        if not self.available:
            return default
        with self._lock:
            try:
                with self._connect(include_db=True) as conn:
                    with conn.cursor() as cur:
                        cur.execute("SELECT pref_value FROM preferences WHERE pref_key=%s", (key,))
                        row = cur.fetchone()
                if not row:
                    return default
                return json.loads(row[0])
            except Exception as exc:
                logger.error("get_preference failed for key=%s: %s", key, exc)
                return default

    def insert_memory(self, ts: str, kind: str, content_enc: str) -> bool:
        if not self.available:
            return False
        with self._lock:
            try:
                with self._connect(include_db=True) as conn:
                    with conn.cursor() as cur:
                        cur.execute(
                            "INSERT INTO long_term_memory (ts, kind, content_enc) VALUES (%s, %s, %s)",
                            (ts, kind, content_enc),
                        )
                return True
            except Exception as exc:
                logger.error("insert_memory failed: %s", exc)
                return False

    def latest_memory(self, limit: int = 12) -> list[tuple[str, str, str]]:
        if not self.available:
            return []
        with self._lock:
            try:
                with self._connect(include_db=True) as conn:
                    with conn.cursor() as cur:
                        cur.execute(
                            """
                            SELECT ts, kind, content_enc
                            FROM long_term_memory
                            ORDER BY id DESC
                            LIMIT %s
                            """,
                            (int(limit),),
                        )
                        rows = cur.fetchall() or []
                rows.reverse()
                return [(str(r[0]), str(r[1]), str(r[2])) for r in rows]
            except Exception as exc:
                logger.error("latest_memory failed: %s", exc)
                return []

    def insert_audit(self, ts: str, event_name: str, payload_enc: str) -> bool:
        if not self.available:
            return False
        with self._lock:
            try:
                with self._connect(include_db=True) as conn:
                    with conn.cursor() as cur:
                        cur.execute(
                            "INSERT INTO audit_logs (ts, event_name, payload_enc) VALUES (%s, %s, %s)",
                            (ts, event_name, payload_enc),
                        )
                return True
            except Exception as exc:
                logger.error("insert_audit failed: %s", exc)
                return False

    def latest_audit(self, limit: int = 200) -> list[tuple[str, str, str]]:
        if not self.available:
            return []
        with self._lock:
            try:
                with self._connect(include_db=True) as conn:
                    with conn.cursor() as cur:
                        cur.execute(
                            """
                            SELECT ts, event_name, payload_enc
                            FROM audit_logs
                            ORDER BY id DESC
                            LIMIT %s
                            """,
                            (int(limit),),
                        )
                        rows = cur.fetchall() or []
                rows.reverse()
                return [(str(r[0]), str(r[1]), str(r[2])) for r in rows]
            except Exception as exc:
                logger.error("latest_audit failed: %s", exc)
                return []

    def insert_simulation(
        self,
        ts: str,
        command_name: str,
        risk_level: str,
        impacted_files: list[str],
        process_changes: list[str],
        system_impact: str,
        syscall_intensity: str,
        telemetry_signals: list[str],
        summary: str,
    ) -> bool:
        if not self.available:
            return False
        payload = json.dumps(
            {
                "impacted_files": impacted_files,
                "process_changes": process_changes,
                "system_impact": system_impact,
                "syscall_intensity": syscall_intensity,
                "telemetry_signals": telemetry_signals,
                "summary": summary,
            },
            ensure_ascii=True,
        )
        with self._lock:
            try:
                with self._connect(include_db=True) as conn:
                    with conn.cursor() as cur:
                        cur.execute(
                            """
                            INSERT INTO simulation_logs (ts, command_name, risk_level, payload_json)
                            VALUES (%s, %s, %s, %s)
                            """,
                            (ts, command_name, risk_level, payload),
                        )
                return True
            except Exception as exc:
                logger.error("insert_simulation failed: %s", exc)
                return False

    def insert_syscall_profile(
        self,
        ts: str,
        command_name: str,
        duration_ms: float,
        syscall_intensity: str,
        kernel_transition_cost: str,
        subsystems: list[str],
        ok: bool,
    ) -> bool:
        if not self.available:
            return False
        subsystems_json = json.dumps(subsystems, ensure_ascii=True)
        with self._lock:
            try:
                with self._connect(include_db=True) as conn:
                    with conn.cursor() as cur:
                        cur.execute(
                            """
                            INSERT INTO syscall_profiles
                            (ts, command_name, duration_ms, syscall_intensity, kernel_transition_cost, subsystems_json, success)
                            VALUES (%s, %s, %s, %s, %s, %s, %s)
                            """,
                            (
                                ts,
                                command_name,
                                float(duration_ms),
                                syscall_intensity,
                                kernel_transition_cost,
                                subsystems_json,
                                1 if ok else 0,
                            ),
                        )
                return True
            except Exception as exc:
                logger.error("insert_syscall_profile failed: %s", exc)
                return False

    def insert_repair_attempt(
        self,
        command_name: str,
        attempt_no: int,
        error_text: str,
        success: bool,
    ) -> bool:
        if not self.available:
            return False
        ts = datetime.now(timezone.utc).isoformat()
        with self._lock:
            try:
                with self._connect(include_db=True) as conn:
                    with conn.cursor() as cur:
                        cur.execute(
                            """
                            INSERT INTO repair_attempts (ts, command_name, attempt_no, error_text, success)
                            VALUES (%s, %s, %s, %s, %s)
                            """,
                            (ts, command_name, int(attempt_no), error_text, 1 if success else 0),
                        )
                return True
            except Exception as exc:
                logger.error("insert_repair_attempt failed: %s", exc)
                return False
