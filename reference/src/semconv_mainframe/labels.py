"""
Prometheus label-name helpers.

OTel attribute keys use dots and may contain special characters (e.g.
``mainframe.cpu.type``).  Prometheus label names must be alphanumeric +
underscore.  This module provides the canonical conversion used throughout
the reference scenarios and dashboard PromQL expressions.
"""


def attr_to_label(key: str) -> str:
    """Convert an OTel attribute key to a Prometheus label name.

    Rules (mirrors the OpenTelemetry Collector prometheus exporter):
    - Replace ``.`` and ``-`` with ``_``
    - Replace any remaining non-alphanumeric characters with ``_``
    - Lower-case the result

    Examples::

        attr_to_label("mainframe.cpu.type")        -> "mainframe_cpu_type"
        attr_to_label("network.io.direction")      -> "network_io_direction"
        attr_to_label("mainframe.adapter.port.id") -> "mainframe_adapter_port_id"
    """
    import re
    label = key.replace(".", "_").replace("-", "_")
    label = re.sub(r"[^a-zA-Z0-9_]", "_", label)
    return label.lower()
