import collections

from tornado import httputil


TcpEndpoint = collections.namedtuple('TcpEndpoint', ["host", "port"])


class Endpoints(object):
    unix_prefix = "unix://"
    tcp_prefix = "tcp://"

    def __init__(self, endpoints):
        self.unix = []
        self.tcp = []
        for i in endpoints:
            if i.startswith(Endpoints.unix_prefix):
                self.unix.append(i[len(Endpoints.unix_prefix):])
            elif i.startswith(Endpoints.tcp_prefix):
                raw = i[len(Endpoints.tcp_prefix):]
                delim_count = raw.count(":")
                if delim_count == 0:  # no port
                    raise ValueError("Endpoint has to containt host:port: %s" % i)
                elif delim_count == 1:  # ipv4 or hostname
                    host, _, port = raw.partition(":")
                    self.tcp.append(TcpEndpoint(host=host, port=int(port)))
                elif delim_count > 1:  # ipv6
                    host, _, port = raw.rpartition(":")
                    if host[0] != "[" or host[-1] != "]":
                        raise ValueError("Invalid IPv6 address %s" % i)
                    self.tcp.append(TcpEndpoint(host=host.strip("[]"), port=int(port)))
            else:
                raise ValueError("Endpoint has to begin either unix:// or tcp:// %s" % i)


def fill_response_in(request, code, status, message, headers=None):
    headers = headers or httputil.HTTPHeaders()
    if "Content-Length" not in headers:
        content_length = str(len(message))
        request.logger.debug("Content-Length header was generated by the proxy: %s", content_length)
        headers.add("Content-Length", content_length)

    headers.add("X-Powered-By", "Cocaine")
    headers["X-XSS-Protection"] = "1; mode=block"
    request.logger.debug("Content-Length: %s", headers["Content-Length"])

    if getattr(request, "traceid", None) is not None:
        headers.add("X-Request-Id", request.traceid)

    if request.method == "HEAD":
        message = None

    request.connection.write_headers(
        # start_line
        httputil.ResponseStartLine(request.version, code, status),
        # headers
        headers,
        # data
        message)
    request.connection.finish()
    request.logger.info("finish request: %d %s %.2fms",
                        code, status, 1000.0 * request.request_time())


def pack_httprequest(request):
    headers = [(item.key, item.value) for item in request.cookies.itervalues()]
    headers.extend(request.headers.items())
    packed = request.method, request.uri, request.version.split("/")[1], headers, request.body
    return packed


def parse_locators_endpoints(endpoint):
    host, _, port = endpoint.rpartition(":")
    if host and port:
        try:
            return (host, int(port))
        except ValueError:
            pass

    raise Exception("invalid endpoint: %s" % endpoint)
