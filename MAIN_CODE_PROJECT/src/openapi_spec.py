"""Automatic OpenAPI 3.1 specification generation from module contracts."""

from __future__ import annotations

from typing import Any, Callable, Dict, List, Optional, Set, Tuple, Type, get_type_hints
import datetime
import http.server
import importlib
import inspect
import json
import os
import re
import threading
import uuid


_OPENAPI_VERSION = '3.1.0'
_SERVED_SPEC_PATH = '/openapi.json'


def _py_type_to_schema(py_type: Any) -> Dict[str, Any]:
    origin = getattr(py_type, '__origin__', None)
    args = getattr(py_type, '__args__', ())

    if origin is list:
        items = _py_type_to_schema(args[0]) if args else {}
        return {'type': 'array', 'items': items}
    if origin is dict:
        additional = _py_type_to_schema(args[1]) if len(args) > 1 else {}
        return {'type': 'object', 'additionalProperties': additional}
    if origin is Optional or origin is Union:
        types = [t for t in args if t is not type(None)]
        if types:
            schema = _py_type_to_schema(types[0])
            schema['nullable'] = True
            return schema

    if py_type is str:
        return {'type': 'string'}
    if py_type is int:
        return {'type': 'integer'}
    if py_type is float:
        return {'type': 'number'}
    if py_type is bool:
        return {'type': 'boolean'}
    if py_type is bytes:
        return {'type': 'string', 'format': 'binary'}
    if py_type is datetime.datetime:
        return {'type': 'string', 'format': 'date-time'}
    if py_type is datetime.date:
        return {'type': 'string', 'format': 'date'}
    if py_type is Any:
        return {}

    if inspect.isclass(py_type):
        return _class_to_schema(py_type)

    return {}


def _class_to_schema(cls: type) -> Dict[str, Any]:
    hints = {}
    try:
        hints = get_type_hints(cls)
    except Exception:
        for name in dir(cls):
            if not name.startswith('_'):
                hints[name] = Any

    properties = {}
    required = []
    for name, typ in hints.items():
        if name.startswith('_'):
            continue
        properties[name] = _py_type_to_schema(typ)
        if getattr(typ, '__origin__', None) is not Optional:
            required.append(name)

    schema: Dict[str, Any] = {
        'type': 'object',
        'properties': properties,
    }
    if required:
        schema['required'] = required
    return schema


class EndpointInfo:
    """Describes a single API endpoint."""

    def __init__(self, path: str, method: str, fn: Callable,
                 summary: str = '', tags: Optional[List[str]] = None) -> None:
        self.path = path
        self.method = method.upper()
        self.fn = fn
        self.summary = summary or fn.__name__
        self.tags = tags or []


class SchemaRegistry:
    """Tracks schemas for reuse across the spec ($ref)."""

    def __init__(self) -> None:
        self._schemas: Dict[str, Dict[str, Any]] = {}
        self._lock = threading.Lock()

    def register(self, name: str, schema: Dict[str, Any]) -> str:
        with self._lock:
            if name not in self._schemas:
                self._schemas[name] = schema
            return f'#/components/schemas/{name}'

    def get_all(self) -> Dict[str, Dict[str, Any]]:
        with self._lock:
            return dict(self._schemas)


class OpenAPIGenerator:
    """Generates OpenAPI 3.1 specification from module endpoints."""

    def __init__(self, title: str = 'API', version: str = '1.0.0',
                 description: str = '') -> None:
        self._title = title
        self._version = version
        self._description = description
        self._endpoints: List[EndpointInfo] = []
        self._schemas = SchemaRegistry()
        self._servers: List[Dict[str, str]] = [{'url': 'http://localhost:8000'}]

    def add_endpoint(self, endpoint: EndpointInfo) -> None:
        self._endpoints.append(endpoint)

    def add_server(self, url: str, description: str = '') -> None:
        self._servers.append({'url': url, 'description': description} if description else {'url': url})

    def register_schema(self, name: str, schema: Dict[str, Any]) -> None:
        self._schemas.register(name, schema)

    def from_fn(self, path: str, method: str, fn: Callable,
                summary: str = '', tags: Optional[List[str]] = None) -> EndpointInfo:
        ep = EndpointInfo(path, method, fn, summary, tags)
        self.add_endpoint(ep)
        return ep

    def generate(self) -> Dict[str, Any]:
        spec: Dict[str, Any] = {
            'openapi': _OPENAPI_VERSION,
            'info': {
                'title': self._title,
                'version': self._version,
                'description': self._description,
            },
            'servers': self._servers,
            'paths': {},
            'components': {
                'schemas': {},
            },
        }

        for ep in self._endpoints:
            path_item = self._build_path_item(ep)
            if ep.path not in spec['paths']:
                spec['paths'][ep.path] = {}
            spec['paths'][ep.path][ep.method.lower()] = path_item

        spec['components']['schemas'] = self._schemas.get_all()
        return spec

    def _build_path_item(self, ep: EndpointInfo) -> Dict[str, Any]:
        sig = inspect.signature(ep.fn)
        hints = {}
        try:
            hints = get_type_hints(ep.fn)
        except Exception:
            for p in sig.parameters:
                hints[p] = Any

        parameters = []
        request_body = None
        for name, param in sig.parameters.items():
            if name in ('self', 'cls'):
                continue
            ptype = hints.get(name, Any)
            if param.kind in (inspect.Parameter.POSITIONAL_ONLY, inspect.Parameter.POSITIONAL_OR_KEYWORD):
                if name in ep.path:
                    parameters.append({
                        'name': name,
                        'in': 'path',
                        'required': True,
                        'schema': _py_type_to_schema(ptype),
                    })
                else:
                    parameters.append({
                        'name': name,
                        'in': 'query',
                        'required': param.default is inspect.Parameter.empty,
                        'schema': _py_type_to_schema(ptype),
                    })

        return_annotation = sig.return_annotation
        if return_annotation is not inspect.Parameter.empty and return_annotation is not None:
            return_schema = _py_type_to_schema(return_annotation)
        else:
            return_schema = {}

        examples = self._generate_examples(ep.fn)

        path_item: Dict[str, Any] = {
            'summary': ep.summary,
            'operationId': ep.fn.__name__,
            'tags': ep.tags or [],
            'parameters': parameters,
            'responses': {
                '200': {
                    'description': 'Successful response',
                    'content': {
                        'application/json': {
                            'schema': return_schema,
                            'example': examples.get('response'),
                        },
                    },
                },
                '400': {
                    'description': 'Bad request',
                },
            },
        }

        if request_body:
            path_item['requestBody'] = request_body

        return path_item

    def _generate_examples(self, fn: Callable) -> Dict[str, Any]:
        sig = inspect.signature(fn)
        examples: Dict[str, Any] = {'response': {}}

        try:
            src = inspect.getsource(fn)
            doc_str = inspect.getdoc(fn) or ''
            example_match = re.search(r'@example\s+(\{.*\})', src, re.DOTALL)
            if example_match:
                try:
                    examples['response'] = json.loads(example_match.group(1))
                except json.JSONDecodeError:
                    pass
        except Exception:
            pass

        return examples

    def export_json(self, path: str) -> None:
        spec = self.generate()
        with open(path, 'w') as f:
            json.dump(spec, f, indent=2, default=str)

    def export_yaml(self, path: str) -> None:
        spec = self.generate()
        lines = []
        def _to_yaml(obj, indent=0):
            prefix = ' ' * indent
            if isinstance(obj, dict):
                for k, v in obj.items():
                    if isinstance(v, (dict, list)):
                        lines.append(f'{prefix}{k}:')
                        _to_yaml(v, indent + 2)
                    else:
                        lines.append(f'{prefix}{k}: {json.dumps(v, default=str)}')
            elif isinstance(obj, list):
                for item in obj:
                    if isinstance(item, (dict, list)):
                        lines.append(f'{prefix}-')
                        _to_yaml(item, indent + 2)
                    else:
                        lines.append(f'{prefix}- {json.dumps(item, default=str)}')
        _to_yaml(spec)
        with open(path, 'w') as f:
            f.write('\n'.join(lines))


class OpenAPIServer:
    """Serves the generated OpenAPI spec and Swagger UI."""

    def __init__(self, spec: Dict[str, Any], host: str = '0.0.0.0', port: int = 8080) -> None:
        self._spec = spec
        self._host = host
        self._port = port
        self._server: Optional[http.server.HTTPServer] = None
        self._thread: Optional[threading.Thread] = None

    def start(self) -> None:
        class Handler(http.server.BaseHTTPRequestHandler):
            spec = self._spec

            def do_GET(self):
                if self.path == _SERVED_SPEC_PATH:
                    self.send_response(200)
                    self.send_header('Content-Type', 'application/json')
                    self.send_header('Access-Control-Allow-Origin', '*')
                    self.end_headers()
                    self.wfile.write(json.dumps(spec, default=str).encode('utf-8'))
                elif self.path in ('/', '/docs'):
                    self.send_response(200)
                    self.send_header('Content-Type', 'text/html; charset=utf-8')
                    self.end_headers()
                    self.wfile.write(SwaggerUIHTML.encode('utf-8'))
                else:
                    self.send_response(404)
                    self.end_headers()

            def log_message(self, fmt, *args):
                pass

        self._server = http.server.HTTPServer((self._host, self._port), Handler)
        self._thread = threading.Thread(target=self._server.serve_forever, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        if self._server:
            self._server.shutdown()


SwaggerUIHTML = """<!DOCTYPE html>
<html>
<head><title>API Docs</title>
<link rel="stylesheet" href="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui.css">
</head>
<body><div id="swagger-ui"></div>
<script src="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5/swagger-ui-bundle.js"></script>
<script>
SwaggerUIBundle({ url: '/openapi.json', dom_id: '#swagger-ui' });
</script>
</body>
</html>"""


class OpenAPIOrchestrator:
    """Top-level orchestrator for OpenAPI spec generation and serving."""

    def __init__(self, title: str = 'BaseApp API', version: str = '1.0.0') -> None:
        self._generator = OpenAPIGenerator(title, version)
        self._server: Optional[OpenAPIServer] = None

    @property
    def generator(self) -> OpenAPIGenerator:
        return self._generator

    def register_endpoint(self, path: str, method: str, fn: Callable,
                          summary: str = '', tags: Optional[List[str]] = None) -> EndpointInfo:
        return self._generator.from_fn(path, method, fn, summary, tags)

    def register_schema(self, name: str, cls: type) -> str:
        schema = _class_to_schema(cls)
        return self._generator._schemas.register(name, schema)

    def generate_spec(self) -> Dict[str, Any]:
        return self._generator.generate()

    def export_spec(self, path: str, fmt: str = 'json') -> None:
        if fmt == 'json':
            self._generator.export_json(path)
        else:
            self._generator.export_yaml(path)

    def serve_docs(self, host: str = '0.0.0.0', port: int = 8080) -> OpenAPIServer:
        spec = self.generate_spec()
        self._server = OpenAPIServer(spec, host, port)
        self._server.start()
        return self._server

    def stop_server(self) -> None:
        if self._server:
            self._server.stop()

    def export_artifacts(self, dir: str) -> List[str]:
        os.makedirs(dir, exist_ok=True)
        paths = []
        jp = os.path.join(dir, 'openapi.json')
        self.export_spec(jp, 'json')
        paths.append(jp)
        return paths
