from prometheus_client import make_wsgi_app
from prometheus_client.core import GaugeMetricFamily, REGISTRY

from wsgiref.simple_server import make_server


DEFAULT_METRICS_PORT = 9789


class PrusaCollector(object):
	def __init__(self, hostname):
		if not hostname:
			raise ValueError("No hostname specified!")
		self.hostname = hostname

	def collect(self):
		yield GaugeMetricFamily("some_gauge", "This is the help text", value=4)


def start_server(port=DEFAULT_METRICS_PORT, address='', registry=REGISTRY):
	app = make_wsgi_app(registry)
	with make_server(address, port, app) as httpd:
		print("Starting httpd...")
		httpd.serve_forever()


if __name__ == '__main__':
	import os

	port = os.environ.get("METRICS_PORT", DEFAULT_METRICS_PORT)
	printer_hostname = os.environ.get("PRINTER_HOSTNAME", None)

	collector = PrusaCollector(printer_hostname)
	REGISTRY.register(collector)
	start_server(port, registry=REGISTRY)
