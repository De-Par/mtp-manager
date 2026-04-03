from __future__ import annotations

from infra.shell import ShellRunner
from models.health import HealthCheck, HealthReport, Severity
from models.settings import AppSettings
from paths import ProjectPaths
from services.inventory_service import InventoryService
from services.network_service import NetworkService
from services.systemd_service import SystemdService


class DiagnosticsService:
    def __init__(
        self,
        network: NetworkService,
        inventory: InventoryService,
        systemd: SystemdService,
        shell: ShellRunner,
        paths: ProjectPaths,
    ) -> None:
        self.network = network
        self.inventory = inventory
        self.systemd = systemd
        self.shell = shell
        self.paths = paths

    def build_report(self, settings: AppSettings) -> HealthReport:
        checks = [
            HealthCheck("public_ip", "Public IP", self.network.detect_public_ip() or "unknown", Severity.INFO),
            HealthCheck("telemt_version", "telemt", self.installed_version(), Severity.INFO),
            HealthCheck("mt_port", "Proxy port", str(settings.mt_port), Severity.INFO),
            HealthCheck("stats_port", "API port", str(settings.stats_port), Severity.INFO),
            HealthCheck("fake_tls", "Fake TLS", settings.fake_tls_domain or "disabled", Severity.OK if settings.fake_tls_domain else Severity.WARN),
            HealthCheck("enabled_secrets", "Enabled secrets", str(self.inventory.enabled_secret_count()), Severity.INFO),
            HealthCheck("service_status", "Service status", self.systemd.state(), Severity.INFO),
        ]
        return HealthReport(checks=checks)

    def installed_version(self) -> str:
        binary = self.paths.binary_file
        if not binary.exists():
            return "not-installed"
        for args in ([str(binary), "--version"], [str(binary), "-V"]):
            result = self.shell.run(args, check=False)
            output = (result.stdout or result.stderr or "").strip()
            if output:
                return self._normalize_version(output.splitlines()[0].strip())
        return "unknown"

    @staticmethod
    def _normalize_version(raw_value: str) -> str:
        parts = raw_value.split()
        if len(parts) >= 2 and parts[0].lower() == "telemt":
            return parts[1]
        return raw_value
