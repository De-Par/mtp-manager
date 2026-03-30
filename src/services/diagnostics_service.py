from __future__ import annotations

from models.health import HealthCheck, HealthReport, Severity
from models.settings import AppSettings
from services.inventory_service import InventoryService
from services.network_service import NetworkService
from services.systemd_service import SystemdService


class DiagnosticsService:
    def __init__(
        self,
        network: NetworkService,
        inventory: InventoryService,
        systemd: SystemdService,
    ) -> None:
        self.network = network
        self.inventory = inventory
        self.systemd = systemd

    def build_report(self, settings: AppSettings) -> HealthReport:
        checks = [
            HealthCheck("public_ip", "Public IP", self.network.detect_public_ip() or "unknown", Severity.INFO),
            HealthCheck("mt_port", "Client port", str(settings.mt_port), Severity.INFO),
            HealthCheck("stats_port", "Stats port", str(settings.stats_port), Severity.INFO),
            HealthCheck("fake_tls", "Fake TLS", settings.fake_tls_domain or "disabled", Severity.OK if settings.fake_tls_domain else Severity.WARN),
            HealthCheck("enabled_secrets", "Enabled secrets", str(self.inventory.enabled_secret_count()), Severity.INFO),
            HealthCheck("service_status", "Service status", self.systemd.state(), Severity.INFO),
        ]
        return HealthReport(checks=checks)
