from prometheus_client import make_wsgi_app
from prometheus_client.core import GaugeMetricFamily, REGISTRY
from wsgiref.simple_server import make_server


class PrusaCollector(object):
	def collect(self):
		yield GaugeMetricFamily("some_gauge", "This is the help text", value=4)


REGISTRY.register(PrusaCollector())


def start_server(port, address='', registry=REGISTRY):
	app = make_wsgi_app(registry)
	with make_server(address, port, app) as httpd:
		httpd.serve_forever()


if __name__ == '__main__':
	start_server(8080)