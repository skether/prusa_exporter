import re
from wsgiref.simple_server import make_server

from prometheus_client import make_wsgi_app
from prometheus_client.core import GaugeMetricFamily, InfoMetricFamily, REGISTRY

import requests


DEFAULT_METRICS_PORT = 9789


"""
Example data returned by Prusa Mini Telemetry

During printing:
{
    'temp_nozzle': 215,             // Implemented as prusa_temperature_celsius{sensor="nozzle"}
    'temp_bed': 60,                 // Implemented as prusa_temperature_celsius{sensor="bed"}
    'material': 'PLA',              // Implemented as prusa_material_info{material="X"}
    'pos_z_mm': 6.48,               // Implemented as prusa_position_meter{axis="z"}
    'printing_speed': 100,          // Implemented as prusa_print_speed_percent
    'flow_factor': 100,             // Implemented as prusa_flow_factor_percent
    'progress': 87,                 // Implemented as prusa_print_job_progress_percent{project="X"}
    'print_dur': '  1d  0h 54m',    // Implemented as prusa_print_job_elapsed_time_seconds{project="X"}
    'time_est': '13380',            // Implemented as prusa_print_job_remaining_time_seconds{project="X"}
    'time_zone': '1',               // Not useful
    'project_name': 'Nasa_Chainmail_15x15-HandCrafted-lowres_0.25n_0.15mm_PLA_MINI_1d5h3m.gcode'
                                    // Included as a label for job metrics
}

Idle:
{
    "temp_nozzle":24,               // Implemented as prusa_temperature_celsius{sensor="nozzle"}
    "temp_bed":25,                  // Implemented as prusa_temperature_celsius{sensor="bed"}
    "material":"PLA",               // Implemented as prusa_material_info{material="X"}
    "pos_z_mm":0.00,                // Implemented as prusa_position_meters{axis="z"}
    "printing_speed":100,           // Implemented as prusa_print_speed_percent
    "flow_factor":100               // Implemented as prusa_flow_factor_percent
}
"""


class PrusaCollector(object):
    def __init__(self, hostname):
        if not hostname:
            raise ValueError("No hostname specified!")
        self.hostname = hostname
        self.prefix = "prusa"

    def collect(self):
        telemetry = self.retrieve_telemetry()

        available = bool(telemetry)
        yield GaugeMetricFamily(f"{self.prefix}_printer_available", "Returns of the printer is available on the network", value=int(available))

        if not available:
            return

        temperature_metric = GaugeMetricFamily(f"{self.prefix}_temperature", "Various temperatures of the printer", labels=["sensor"], unit="celsius")
        temperature_metric.add_metric(["nozzle"], telemetry.get("temp_nozzle"))
        temperature_metric.add_metric(["bed"], telemetry.get("temp_bed"))
        yield temperature_metric

        yield GaugeMetricFamily(f"{self.prefix}_print_speed", "Print speed of the printer", value=telemetry.get("printing_speed") / 100, unit="percent")

        yield GaugeMetricFamily(f"{self.prefix}_flow_factor", "Flow factor", value=telemetry.get("flow_factor") / 100, unit="percent")

        position_metric = GaugeMetricFamily(f"{self.prefix}_position", "Position of the axis", labels=["axis"], unit="millimeters")
        position_metric.add_metric(["z"], telemetry.get("pos_z_mm"))
        yield position_metric

        material = (telemetry.get("material", "")).strip()
        if material and material != "---":
            material_metric = InfoMetricFamily(f"{self.prefix}_material", "Info about the material loaded into the printer")
            material_metric.add_metric([], {"material": telemetry.get("material")})
            yield material_metric

        project = telemetry.get("project_name", None)

        time_str = telemetry.get("print_dur")
        time = None
        if time_str:
            match = re.match(r"^\s*((\d+)d)?\s*((\d+)h)?\s*((\d+)m)?\s*((\d+)s)?\s*$", time_str)
            time = sum((int(match.group(2) or 0) * 24 * 60 * 60, int(match.group(4) or 0) * 60 * 60, int(match.group(6) or 0) * 60, int(match.group(8) or 0)))
        elapsed_time_metric = GaugeMetricFamily(f"{self.prefix}_print_job_elapsed_time", "Time elapsed since the start of the print", labels=["project"], unit="seconds")
        if project:
            elapsed_time_metric.add_metric([project], time)
        yield elapsed_time_metric

        remaining_time_metric = GaugeMetricFamily(f"{self.prefix}_print_job_remaining_time", "Time remaining of the print job", labels=["project"], unit="seconds")
        if project:
            remaining_time_metric.add_metric([project], telemetry.get("time_est"))
        yield remaining_time_metric

        progress = telemetry.get("progress")
        if progress:
            progress /= 100
        progress_metric = GaugeMetricFamily(f"{self.prefix}_print_job_progress", "The percent progress of the print job", labels=["project"], unit="percent")
        if project:
            progress_metric.add_metric([project], progress)
        yield progress_metric

    def describe(self):
        yield GaugeMetricFamily(f"{self.prefix}_printer_available", "Returns of the printer is available on the network")
        yield GaugeMetricFamily(f"{self.prefix}_temperature", "Various temperatures of the printer", labels=["sensor"], unit="celsius")
        yield GaugeMetricFamily(f"{self.prefix}_print_speed", "Print speed of the printer", unit="percent")
        yield GaugeMetricFamily(f"{self.prefix}_flow_factor", "Flow factor", unit="percent")
        yield GaugeMetricFamily(f"{self.prefix}_position", "Position of the axis", labels=["axis"], unit="millimeters")
        yield InfoMetricFamily(f"{self.prefix}_material", "Info about the material loaded into the printer")
        yield GaugeMetricFamily(f"{self.prefix}_print_job_elapsed_time", "Time elapsed since the start of the print", labels=["project"], unit="seconds")
        yield GaugeMetricFamily(f"{self.prefix}_print_job_remaining_time", "Time remaining of the print job", labels=["project"], unit="seconds")
        yield GaugeMetricFamily(f"{self.prefix}_print_job_progress", "The percent progress of the print job", labels=["project"], unit="percent")

    def retrieve_telemetry(self):
        try:
            r = requests.get(f"http://{self.hostname}/api/telemetry", timeout=5)
            if r.status_code == requests.codes.ok:
                telemetry = r.json()
                print(f"Telemetry received: {telemetry}")
                return telemetry
            print(f"Telemetry error: {r.status_code}")
            return None
        except requests.Timeout:
            print("Telemetry request timeout!")
            return None
        except Exception as e:
            print("An exception occured while retrieving telemetry! ")
            print(e)
            return None


def start_server(port=DEFAULT_METRICS_PORT, address="", registry=REGISTRY):
    app = make_wsgi_app(registry)
    with make_server(address, port, app) as httpd:
        print("Starting httpd...")
        httpd.serve_forever()


def shutdown(signal, _):
    import sys
    print(f"Signal ({signal}) received! Shutting down...")
    sys.exit(0)


def main():
    import os
    import signal

    signal.signal(signal.SIGINT, shutdown)
    signal.signal(signal.SIGTERM, shutdown)

    port = os.environ.get("METRICS_PORT", DEFAULT_METRICS_PORT)
    printer_hostname = os.environ.get("PRINTER_HOSTNAME", None)

    collector = PrusaCollector(printer_hostname)
    REGISTRY.register(collector)
    start_server(port, registry=REGISTRY)


if __name__ == "__main__":
    main()
