"""
Synthetic metric emitters for every mainframe semantic convention metric.

Each emitter class covers one cluster of entity types and emits exactly the
metrics defined in the corresponding model/mainframe/*.yaml files, using
deterministic synthetic values.  The values are designed to be realistic
enough to exercise unit and attribute label rendering in Grafana dashboards.

Metric → Prometheus name mapping (per OpenTelemetry Collector convention):
  dots and hyphens in the metric name are replaced with underscores.
  e.g. ``mainframe.host.cpu.active.count`` → ``mainframe_host_cpu_active_count``

All attribute values (labels) follow the same convention so that the
PromQL expressions in dashboards/mainframe/*.json resolve correctly.
"""
from __future__ import annotations

from opentelemetry import metrics as otel_metrics
from opentelemetry.sdk.metrics import MeterProvider


# ---------------------------------------------------------------------------
# Constants — synthetic CPC / partition identifiers
# ---------------------------------------------------------------------------
_CPC_NAME = "CPC01"
_CPC_MACHINE_TYPE = "3931"
_CPC_MACHINE_MODEL = "A01"
_CPC_SERIAL = "0000000AA01"

_PARTITIONS = ["LPAR01", "LPAR02"]
_CPU_TYPES_CPC = ["cp", "ifl", "iip", "icf"]   # types with active processors
_CPU_TYPES_PARTITION = ["cp", "ifl"]
_SHARING_MODES = ["shared", "dedicated"]
_ADAPTER_TYPES = ["network", "storage", "crypto", "accelerator"]
_ADAPTER_NAME = "0.2D"
_PORT_ID = "0"
_NIC_NAME = "nic-0"
_STORAGE_GROUP = "sg-fcp-prod"
_STORAGE_VOLUME = "vol-boot-0"


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------
def _meter(provider: MeterProvider, name: str) -> otel_metrics.Meter:
    return provider.get_meter(name, "0.1.0")


# ===========================================================================
# Host emitter  (model/mainframe/metrics_host.yaml)
# ===========================================================================
class MainframeHostEmitter:
    """Emits all ``mainframe.host.*`` metrics defined in metrics_host.yaml.

    Entity: ``mainframe.host``, identified by ``host.name`` = CPC name.
    """

    def __init__(self, provider: MeterProvider) -> None:
        meter = _meter(provider, "semconv_mainframe.host")

        # --- processor counts (mainframe.host.cpu.active.count) --------------
        self._cpu_active = meter.create_up_down_counter(
            "mainframe.host.cpu.active.count",
            unit="{cpu}",
            description="The number of active processors of the specified type installed in the mainframe system.",
        )
        self._cpu_defective = meter.create_up_down_counter(
            "mainframe.host.cpu.defective.count",
            unit="{cpu}",
            description="The number of defective processors in the mainframe system.",
        )
        self._cpu_spare = meter.create_up_down_counter(
            "mainframe.host.cpu.spare.count",
            unit="{cpu}",
            description="The number of spare processors available in the mainframe system.",
        )

        # --- memory sizes (mainframe.host.memory.size) -----------------------
        self._memory_size = meter.create_gauge(
            "mainframe.host.memory.size",
            unit="MiBy",
            description="The size of memory of the specified category in the mainframe system.",
        )
        self._memory_vfm_increment = meter.create_gauge(
            "mainframe.host.memory.vfm.increment.size",
            unit="GiBy",
            description="The size of one IBM Virtual Flash Memory (VFM) increment in the mainframe system.",
        )
        self._memory_vfm_total = meter.create_gauge(
            "mainframe.host.memory.vfm.size",
            unit="GiBy",
            description="The total size of installed IBM Virtual Flash Memory (VFM) in the mainframe system.",
        )

        # --- channel + CPU utilization ---------------------------------------
        self._channel_util = meter.create_gauge(
            "mainframe.host.channel.utilization",
            unit="1",
            description="The average fraction of time all channels in the mainframe system were busy processing I/O.",
        )
        self._cpu_util = meter.create_gauge(
            "mainframe.host.cpu.utilization",
            unit="1",
            description="The fraction of time processors of the specified type in the mainframe system were busy executing work.",
        )

        # --- environmental ---------------------------------------------------
        self._temperature = meter.create_gauge(
            "mainframe.host.temperature",
            unit="Cel",
            description="The temperature at the specified sensor location of the mainframe system in degrees Celsius.",
        )
        self._humidity = meter.create_gauge(
            "mainframe.host.humidity",
            unit="1",
            description="The relative humidity of the environment surrounding the mainframe system.",
        )
        self._dewpoint = meter.create_gauge(
            "mainframe.host.dewpoint",
            unit="Cel",
            description="The dew point temperature of the environment surrounding the mainframe system in degrees Celsius.",
        )
        self._heatload = meter.create_gauge(
            "mainframe.host.heatload",
            unit="J/h",
            description="The heat load produced by the mainframe system, measured in joules per hour.",
        )

        # --- power -----------------------------------------------------------
        self._power_usage = meter.create_gauge(
            "mainframe.host.power.usage",
            unit="W",
            description="The power consumption of the mainframe system in Watts.",
        )
        self._power_cord = meter.create_gauge(
            "mainframe.host.power.cord.usage",
            unit="W",
            description="The power consumption on the specified power cord of the mainframe system in Watts.",
        )

        # --- status ----------------------------------------------------------
        self._status_code = meter.create_gauge(
            "mainframe.host.status.code",
            unit="1",
            description="The operational status of the mainframe system as a numeric code.",
        )
        self._status_unacceptable = meter.create_gauge(
            "mainframe.host.status.unacceptable",
            unit="1",
            description="Indicates whether the Central Processing Complex (CPC) is in an unacceptable status.",
        )

        # --- DPM adapter utilization -----------------------------------------
        self._adapter_util = meter.create_gauge(
            "mainframe.host.adapter.utilization",
            unit="1",
            description="The fraction of time adapters of the specified type on the mainframe system were busy.",
        )

    def emit(self) -> None:
        """Record one round of synthetic data points for all host metrics."""
        base = {"host.name": _CPC_NAME}

        # processor counts: ifl=10, cp=4, iip=6, icf=2
        counts = {"ifl": 10, "cp": 4, "iip": 6, "icf": 2}
        for cpu_type, count in counts.items():
            self._cpu_active.add(count, {**base, "mainframe.cpu.type": cpu_type})
        self._cpu_defective.add(0, base)
        self._cpu_spare.add(2, base)

        # memory
        mem = {
            "total": 1_048_576, "hsa": 65_536, "partitions": 786_432,
            "central": 524_288, "expanded": 131_072, "available": 262_144,
        }
        for mem_type, size in mem.items():
            self._memory_size.set(size, {**base, "mainframe.memory.type": mem_type})
        self._memory_vfm_increment.set(64, base)
        self._memory_vfm_total.set(512, base)

        # utilization
        self._channel_util.set(0.15, base)
        for cpu_type in _CPU_TYPES_CPC:
            for sharing in _SHARING_MODES:
                val = 0.42 if cpu_type == "ifl" else 0.18
                self._cpu_util.set(val, {**base,
                    "mainframe.cpu.type": cpu_type,
                    "mainframe.cpu.sharing.mode": sharing,
                })

        # environmental
        self._temperature.set(22.5, {**base, "mainframe.host.temperature.type": "ambient"})
        self._temperature.set(28.3, {**base, "mainframe.host.temperature.type": "exhaust"})
        self._humidity.set(0.45, base)
        self._dewpoint.set(10.2, base)
        # 3_000 BTU/h × 1055.06 J/BTU = 3_165_180 J/h
        self._heatload.set(3_165_180.0, {**base, "mainframe.host.heatload.type": "total"})
        self._heatload.set(2_110_120.0, {**base, "mainframe.host.heatload.type": "forced-air"})
        self._heatload.set(1_055_060.0, {**base, "mainframe.host.heatload.type": "water"})

        # power (kW → W, already converted)
        power = {"total": 12_000, "partitions": 9_000, "infrastructure": 2_500, "unassigned": 500}
        for ptype, watts in power.items():
            self._power_usage.set(watts, {**base, "mainframe.host.power.usage.type": ptype})
        for cord in ["1", "2"]:
            for phase in ["A", "B", "C"]:
                self._power_cord.set(2_000, {**base,
                    "mainframe.host.power.cord": cord,
                    "mainframe.host.power.phase": phase,
                })

        # status: 0 = operating/active
        self._status_code.set(0, base)
        self._status_unacceptable.set(0, base)

        # DPM adapter utilization
        for adapter_type in _ADAPTER_TYPES:
            val = 0.35 if adapter_type == "network" else 0.20
            self._adapter_util.set(val, {**base, "mainframe.adapter.type": adapter_type})


# ===========================================================================
# Partition emitter  (metrics_partition.yaml + metrics_partition_usage.yaml)
# ===========================================================================
class MainframePartitionEmitter:
    """Emits all ``mainframe.partition.*`` and ``mainframe.cpu.*`` metrics.

    Covers:
    - metrics_partition.yaml  (virtual processor counts, capping, weights)
    - metrics_partition_usage.yaml  (CPU/adapter utilization, memory, status, WLM, …)
    - metrics_cpu.yaml  (per-physical-CPU utilization + SMT metrics)
    - metrics_channel.yaml  (channel utilization)
    """

    def __init__(self, provider: MeterProvider) -> None:
        meter = _meter(provider, "semconv_mainframe.partition")

        # --- partition virtual processor counts ------------------------------
        self._vproc_count = meter.create_up_down_counter(
            "mainframe.partition.cpu.virtual.count",
            unit="{cpu}",
            description="The number of virtual processors of the specified type allocated to an active logical partition.",
        )
        self._is_capped = meter.create_gauge(
            "mainframe.partition.cpu.is_capped",
            unit="1",
            description="Indicates whether absolute capping is enabled for processors of the specified type.",
        )
        self._capped_count = meter.create_up_down_counter(
            "mainframe.partition.cpu.capped.count",
            unit="{cpu}",
            description="The maximum number of processors the logical partition may use when absolute capping is enabled.",
        )
        self._reserved_count = meter.create_up_down_counter(
            "mainframe.partition.cpu.reserved.count",
            unit="{cpu}",
            description="The number of processors of the specified type reserved for the active logical partition.",
        )
        self._weight_value = meter.create_gauge(
            "mainframe.partition.cpu.weight.value",
            unit="1",
            description="The processor scheduling weight of the active logical partition.",
        )
        self._weight_is_capped = meter.create_gauge(
            "mainframe.partition.cpu.weight.is_capped",
            unit="1",
            description="Indicates whether the initial CP processing weight of the logical partition is capped.",
        )

        # --- partition usage: CPU + adapter utilization ----------------------
        self._cpu_util = meter.create_gauge(
            "mainframe.partition.cpu.utilization",
            unit="1",
            description="The fraction of time processors of the specified type allocated to the LPAR were busy.",
        )
        self._adapter_util = meter.create_gauge(
            "mainframe.partition.adapter.utilization",
            unit="1",
            description="The fraction of time adapters of the specified type attached to the LPAR were busy.",
        )
        self._zvm_paging = meter.create_gauge(
            "mainframe.partition.zvm.paging.rate",
            unit="{page}/s",
            description="The z/VM paging rate for the logical partition in pages per second.",
        )
        self._power = meter.create_gauge(
            "mainframe.partition.power.usage",
            unit="W",
            description="The power consumption of the logical partition in Watts.",
        )

        # --- partition status ------------------------------------------------
        self._status_code = meter.create_gauge(
            "mainframe.partition.status.code",
            unit="1",
            description="The operational status of the logical partition as a numeric code.",
        )
        self._status_unacceptable = meter.create_gauge(
            "mainframe.partition.status.unacceptable",
            unit="1",
            description="Indicates whether the logical partition is in an unacceptable status.",
        )

        # --- partition memory ------------------------------------------------
        self._memory_size = meter.create_gauge(
            "mainframe.partition.memory.size",
            unit="MiBy",
            description="The size of the specified memory allocation for the logical partition in mebibytes.",
        )

        # --- classic-mode WLM/capacity/mode ----------------------------------
        self._capacity_defined = meter.create_gauge(
            "mainframe.partition.capacity.defined",
            unit="{MSU}/h",
            description="The defined capacity of the classic-mode LPAR expressed in MSU per hour.",
        )
        self._wlm_enabled = meter.create_gauge(
            "mainframe.partition.wlm.enabled",
            unit="1",
            description="Indicates whether z/OS WLM is permitted to adjust processor weights.",
        )
        self._cpu_mode = meter.create_gauge(
            "mainframe.partition.cpu.mode",
            unit="1",
            description="The processor allocation mode of the DPM partition (0=shared, 1=dedicated).",
        )
        self._threads_per_proc = meter.create_gauge(
            "mainframe.partition.cpu.threads_per_processor",
            unit="{thread}",
            description="The number of SMT threads per processor the DPM partition OS uses.",
        )

        # --- physical CPU metrics (metrics_cpu.yaml) -------------------------
        self._cpu_utilization = meter.create_gauge(
            "mainframe.cpu.utilization",
            unit="1",
            description="The fraction of time the mainframe processor was busy executing work.",
        )
        self._cpu_smt_mode = meter.create_gauge(
            "mainframe.cpu.smt_mode.utilization",
            unit="1",
            description="The fraction of time the processor was running in SMT mode.",
        )
        self._cpu_thread0 = meter.create_gauge(
            "mainframe.cpu.thread0.utilization",
            unit="1",
            description="The fraction of time thread 0 was busy when the processor ran in SMT mode.",
        )
        self._cpu_thread1 = meter.create_gauge(
            "mainframe.cpu.thread1.utilization",
            unit="1",
            description="The fraction of time thread 1 was busy when the processor ran in SMT mode.",
        )

        # --- channel utilization (metrics_channel.yaml) ----------------------
        self._channel_util = meter.create_gauge(
            "mainframe.channel.utilization",
            unit="1",
            description="The fraction of time the I/O channel was busy processing I/O.",
        )

    def emit(self) -> None:
        """Record one round of synthetic partition + CPU + channel data points."""
        for lpar in _PARTITIONS:
            pbase = {"mainframe.partition.name": lpar, "host.name": _CPC_NAME}

            # virtual processor counts
            for cpu_type in _CPU_TYPES_PARTITION:
                count = 4 if cpu_type == "ifl" else 2
                self._vproc_count.add(count, {**pbase, "mainframe.cpu.type": cpu_type})
                self._is_capped.set(0, {**pbase, "mainframe.cpu.type": cpu_type})
                self._capped_count.add(0, {**pbase, "mainframe.cpu.type": cpu_type})
                self._reserved_count.add(0, {**pbase, "mainframe.cpu.type": cpu_type})

            # processor weights
            weights = {"initial": 100, "minimum": 10, "current": 95, "maximum": 200}
            for wtype, val in weights.items():
                self._weight_value.set(val, {**pbase, "mainframe.partition.weight.type": wtype})
            self._weight_is_capped.set(0, pbase)

            # utilization
            for cpu_type in _CPU_TYPES_PARTITION:
                self._cpu_util.set(0.42, {**pbase, "mainframe.cpu.type": cpu_type})
            for adapter_type in ["network", "storage", "crypto", "accelerator"]:
                self._adapter_util.set(0.25, {**pbase, "mainframe.adapter.type": adapter_type})

            self._zvm_paging.set(0.0, pbase)  # not z/VM
            self._power.set(2_500.0, pbase)

            # status: 0 = operating/active
            self._status_code.set(0, pbase)
            self._status_unacceptable.set(0, pbase)

            # memory
            mem_types = {
                "central-initial": 65_536, "central-current": 65_536,
                "central-maximum": 131_072, "expanded-initial": 0,
                "expanded-current": 0, "expanded-maximum": 0,
            }
            for mtype, val in mem_types.items():
                self._memory_size.set(val, {**pbase, "mainframe.partition.memory.type": mtype})

            # WLM / DPM
            self._capacity_defined.set(500, pbase)
            self._wlm_enabled.set(1, pbase)
            self._cpu_mode.set(0, pbase)          # 0 = shared
            self._threads_per_proc.set(2, pbase)  # SMT-2

        # physical CPUs (entity: mainframe.cpu, identified by mainframe.cpu.name)
        for i, cpu_type in enumerate(["IFL", "IFL", "CP"]):
            cbase = {
                "mainframe.cpu.name": f"{cpu_type}{i:02d}",
                "mainframe.cpu.type": cpu_type.lower(),
                "host.name": _CPC_NAME,
            }
            self._cpu_utilization.set(0.55 if cpu_type == "IFL" else 0.30, cbase)
            self._cpu_smt_mode.set(0.80, cbase)
            self._cpu_thread0.set(0.60, cbase)
            self._cpu_thread1.set(0.40, cbase)

        # channel
        self._channel_util.set(
            0.15,
            {
                "mainframe.channel.name": "0.2D",
                "mainframe.channel.mode": "shared",
                "host.name": _CPC_NAME,
            },
        )


# ===========================================================================
# Network emitter  (metrics_nic.yaml + metrics_port.yaml + metrics_adapter.yaml)
# ===========================================================================
class MainframeNetworkEmitter:
    """Emits all NIC, physical port, and adapter utilization metrics.

    Covers:
    - metrics_nic.yaml   (mainframe.partition.nic.* — DPM virtual NIC)
    - metrics_port.yaml  (mainframe.adapter.port.* — DPM physical port)
    - metrics_adapter.yaml  (mainframe.adapter.utilization — all modes)
    """

    def __init__(self, provider: MeterProvider) -> None:
        meter = _meter(provider, "semconv_mainframe.network")

        # --- virtual NIC counters/gauges (metrics_nic.yaml) ------------------
        self._nic_bytes_sent = meter.create_counter(
            "mainframe.partition.nic.bytes.sent", unit="By",
            description="The total number of bytes in unicast packets sent through the virtual NIC.")
        self._nic_bytes_recv = meter.create_counter(
            "mainframe.partition.nic.bytes.received", unit="By",
            description="The total number of bytes in unicast packets received through the virtual NIC.")
        self._nic_pkts_sent = meter.create_counter(
            "mainframe.partition.nic.packets.sent", unit="{packet}",
            description="The total number of unicast packets sent through the virtual NIC.")
        self._nic_pkts_recv = meter.create_counter(
            "mainframe.partition.nic.packets.received", unit="{packet}",
            description="The total number of unicast packets received through the virtual NIC.")
        self._nic_pkts_dropped = meter.create_counter(
            "mainframe.partition.nic.packets.dropped", unit="{packet}",
            description="The total number of packets dropped on the virtual NIC due to resource shortage.")
        self._nic_pkts_discarded = meter.create_counter(
            "mainframe.partition.nic.packets.discarded", unit="{packet}",
            description="The total number of malformed packets discarded on the virtual NIC.")
        self._nic_mcast_sent = meter.create_counter(
            "mainframe.partition.nic.multicast.packets.sent", unit="{packet}",
            description="The total number of multicast packets sent through the virtual NIC.")
        self._nic_mcast_recv = meter.create_counter(
            "mainframe.partition.nic.multicast.packets.received", unit="{packet}",
            description="The total number of multicast packets received through the virtual NIC.")
        self._nic_bcast_sent = meter.create_counter(
            "mainframe.partition.nic.broadcast.packets.sent", unit="{packet}",
            description="The total number of broadcast packets sent through the virtual NIC.")
        self._nic_bcast_recv = meter.create_counter(
            "mainframe.partition.nic.broadcast.packets.received", unit="{packet}",
            description="The total number of broadcast packets received through the virtual NIC.")
        self._nic_data_sent = meter.create_gauge(
            "mainframe.partition.nic.data.sent", unit="By",
            description="The number of bytes sent through the virtual NIC during the last collection interval.")
        self._nic_data_recv = meter.create_gauge(
            "mainframe.partition.nic.data.received", unit="By",
            description="The number of bytes received through the virtual NIC during the last collection interval.")
        self._nic_rate_sent = meter.create_gauge(
            "mainframe.partition.nic.data.rate.sent", unit="By/s",
            description="The data transmission rate of the virtual NIC in bytes per second.")
        self._nic_rate_recv = meter.create_gauge(
            "mainframe.partition.nic.data.rate.received", unit="By/s",
            description="The data reception rate of the virtual NIC in bytes per second.")

        # --- physical port counters/gauges (metrics_port.yaml) ---------------
        self._port_bytes_sent = meter.create_counter(
            "mainframe.adapter.port.bytes.sent", unit="By",
            description="The total number of bytes in unicast packets sent through the physical network adapter port.")
        self._port_bytes_recv = meter.create_counter(
            "mainframe.adapter.port.bytes.received", unit="By",
            description="The total number of bytes in unicast packets received through the physical network adapter port.")
        self._port_pkts_sent = meter.create_counter(
            "mainframe.adapter.port.packets.sent", unit="{packet}",
            description="The total number of unicast packets sent through the physical network adapter port.")
        self._port_pkts_recv = meter.create_counter(
            "mainframe.adapter.port.packets.received", unit="{packet}",
            description="The total number of unicast packets received through the physical network adapter port.")
        self._port_pkts_dropped = meter.create_counter(
            "mainframe.adapter.port.packets.dropped", unit="{packet}",
            description="The total number of packets dropped on the physical network adapter port.")
        self._port_pkts_discarded = meter.create_counter(
            "mainframe.adapter.port.packets.discarded", unit="{packet}",
            description="The total number of malformed packets discarded on the physical network adapter port.")
        self._port_mcast_sent = meter.create_counter(
            "mainframe.adapter.port.multicast.packets.sent", unit="{packet}",
            description="The total number of multicast packets sent through the physical network adapter port.")
        self._port_mcast_recv = meter.create_counter(
            "mainframe.adapter.port.multicast.packets.received", unit="{packet}",
            description="The total number of multicast packets received through the physical network adapter port.")
        self._port_bcast_sent = meter.create_counter(
            "mainframe.adapter.port.broadcast.packets.sent", unit="{packet}",
            description="The total number of broadcast packets sent through the physical network adapter port.")
        self._port_bcast_recv = meter.create_counter(
            "mainframe.adapter.port.broadcast.packets.received", unit="{packet}",
            description="The total number of broadcast packets received through the physical network adapter port.")
        self._port_data_sent = meter.create_gauge(
            "mainframe.adapter.port.data.sent", unit="By",
            description="The number of bytes sent through the physical network adapter port during the last collection interval.")
        self._port_data_recv = meter.create_gauge(
            "mainframe.adapter.port.data.received", unit="By",
            description="The number of bytes received through the physical network adapter port during the last collection interval.")
        self._port_rate_sent = meter.create_gauge(
            "mainframe.adapter.port.data.rate.sent", unit="By/s",
            description="The data transmission rate of the physical network adapter port in bytes per second.")
        self._port_rate_recv = meter.create_gauge(
            "mainframe.adapter.port.data.rate.received", unit="By/s",
            description="The data reception rate of the physical network adapter port in bytes per second.")
        self._port_bw_util = meter.create_gauge(
            "mainframe.adapter.port.bandwidth.utilization", unit="1",
            description="The fraction of the available bandwidth in use on the physical network adapter port.")

        # --- adapter utilization (metrics_adapter.yaml) ----------------------
        self._adapter_util = meter.create_gauge(
            "mainframe.adapter.utilization", unit="1",
            description="The fraction of time the adapter was busy processing I/O or requests.")

    def emit(self) -> None:
        """Record one round of synthetic NIC, port, and adapter data points."""
        # Virtual NIC  (entity: mainframe.partition.nic)
        nic_base = {
            "mainframe.partition.name": _PARTITIONS[0],
            "mainframe.partition.nic.name": _NIC_NAME,
            "mainframe.adapter.name": _ADAPTER_NAME,
            "mainframe.adapter.port.id": _PORT_ID,
            "host.name": _CPC_NAME,
        }
        self._nic_bytes_sent.add(1_234_567_890, nic_base)
        self._nic_bytes_recv.add(9_876_543_210, nic_base)
        self._nic_pkts_sent.add(987_654, nic_base)
        self._nic_pkts_recv.add(1_234_567, nic_base)
        for direction in ["transmit", "receive"]:
            self._nic_pkts_dropped.add(0, {**nic_base, "network.io.direction": direction})
            self._nic_pkts_discarded.add(0, {**nic_base, "network.io.direction": direction})
        self._nic_mcast_sent.add(42, nic_base)
        self._nic_mcast_recv.add(37, nic_base)
        self._nic_bcast_sent.add(5, nic_base)
        self._nic_bcast_recv.add(8, nic_base)
        self._nic_data_sent.set(245_760, nic_base)    # bytes in last interval
        self._nic_data_recv.set(983_040, nic_base)
        self._nic_rate_sent.set(819_200.0, nic_base)  # ~800 KiB/s
        self._nic_rate_recv.set(3_276_800.0, nic_base) # ~3.1 MiB/s

        # Physical port  (entity: mainframe.adapter.port)
        port_base = {
            "mainframe.adapter.name": _ADAPTER_NAME,
            "mainframe.adapter.port.id": _PORT_ID,
            "host.name": _CPC_NAME,
        }
        self._port_bytes_sent.add(5_000_000_000, port_base)
        self._port_bytes_recv.add(12_000_000_000, port_base)
        self._port_pkts_sent.add(4_000_000, port_base)
        self._port_pkts_recv.add(9_600_000, port_base)
        for direction in ["transmit", "receive"]:
            self._port_pkts_dropped.add(0, {**port_base, "network.io.direction": direction})
            self._port_pkts_discarded.add(0, {**port_base, "network.io.direction": direction})
        self._port_mcast_sent.add(200, port_base)
        self._port_mcast_recv.add(180, port_base)
        self._port_bcast_sent.add(20, port_base)
        self._port_bcast_recv.add(25, port_base)
        self._port_data_sent.set(1_048_576, port_base)
        self._port_data_recv.set(4_194_304, port_base)
        self._port_rate_sent.set(3_500_000.0, port_base)   # ~3.3 MiB/s
        self._port_rate_recv.set(14_000_000.0, port_base)  # ~13.4 MiB/s
        self._port_bw_util.set(0.28, port_base)

        # Adapter utilization  (entity: mainframe.adapter)
        adapter_base = {
            "mainframe.adapter.name": _ADAPTER_NAME,
            "mainframe.adapter.type": "network",
            "host.name": _CPC_NAME,
        }
        self._adapter_util.set(0.35, adapter_base)

        # classic-mode per-type adapters
        for atype in ["crypto", "flash", "roce"]:
            self._adapter_util.set(
                0.20 if atype == "crypto" else 0.05,
                {**adapter_base, "mainframe.adapter.type": atype,
                 "mainframe.adapter.name": f"0.{30 + list(['crypto','flash','roce']).index(atype):02X}"},
            )


# ===========================================================================
# Storage emitter  (metrics_storage.yaml)
# ===========================================================================
class MainframeStorageEmitter:
    """Emits all ``mainframe.storage.*`` metrics defined in metrics_storage.yaml.

    Covers storage group, storage volume, and adapter status/channel metrics.
    """

    def __init__(self, provider: MeterProvider) -> None:
        meter = _meter(provider, "semconv_mainframe.storage")

        # --- storage group ---------------------------------------------------
        self._sg_status = meter.create_gauge(
            "mainframe.storage.group.status.code", unit="1",
            description="The fulfillment state of the DPM storage group as a numeric code.")
        self._sg_shared = meter.create_gauge(
            "mainframe.storage.group.shared", unit="1",
            description="Indicates whether the DPM storage group is shared across multiple partitions.")
        self._sg_max_partitions = meter.create_gauge(
            "mainframe.storage.group.max.partitions", unit="{partition}",
            description="The maximum number of DPM partitions to which the FCP storage group can be simultaneously attached.")

        # --- storage volume --------------------------------------------------
        self._sv_status = meter.create_gauge(
            "mainframe.storage.group.volume.status.code", unit="1",
            description="The fulfillment state of the DPM storage volume as a numeric code.")
        self._sv_size = meter.create_gauge(
            "mainframe.storage.group.volume.size", unit="GiBy",
            description="The size of the DPM storage volume in gibibytes.")
        self._sv_cylinders = meter.create_gauge(
            "mainframe.storage.group.volume.cylinders", unit="{cylinder}",
            description="The size of the DPM ECKD storage volume in cylinders.")

        # --- adapter status (DPM, from metrics_storage.yaml) ----------------
        self._adapter_status = meter.create_gauge(
            "mainframe.adapter.status.code", unit="1",
            description="The operational status of the mainframe I/O adapter as a numeric code.")
        self._adapter_channel_status = meter.create_gauge(
            "mainframe.adapter.physical_channel.status.code", unit="1",
            description="The physical channel status of the mainframe I/O adapter as a numeric code.")

    def emit(self) -> None:
        """Record one round of synthetic storage data points."""
        sg_base = {
            "mainframe.storage.group.name": _STORAGE_GROUP,
            "mainframe.storage.group.type": "fcp",
            "host.name": _CPC_NAME,
        }
        self._sg_status.set(0, {**sg_base,
            "mainframe.storage.fulfillment.state": "complete"})   # 0 = complete
        self._sg_shared.set(0, sg_base)         # 0 = not shared
        self._sg_max_partitions.set(4, sg_base)

        sv_base = {
            **sg_base,
            "mainframe.storage.group.volume.name": _STORAGE_VOLUME,
        }
        self._sv_status.set(0, {**sv_base,
            "mainframe.storage.fulfillment.state": "complete"})   # 0 = complete
        self._sv_size.set(200.0, sv_base)       # 200 GiB
        self._sv_cylinders.set(0, sv_base)      # FCP volumes report 0 cylinders

        adapter_base = {
            "mainframe.adapter.name": _ADAPTER_NAME,
            "mainframe.adapter.type": "storage",
            "host.name": _CPC_NAME,
        }
        self._adapter_status.set(0, {**adapter_base,
            "mainframe.adapter.status": "active"})                # 0 = active
        self._adapter_channel_status.set(0, adapter_base)         # 0 = operating
