"""
Dashboard Generator
Generates Grafana dashboards for comprehensive monitoring
"""

import json
from typing import Dict, Any, List, Optional
from datetime import datetime

import structlog


logger = structlog.get_logger(__name__)


class DashboardGenerator:
    """
    Grafana Dashboard Generator
    
    Features:
    - Automatic dashboard generation
    - Real-time metrics visualization
    - Alert rule configuration
    - Custom panel templates
    - Multi-tenant dashboards
    - Performance optimization
    """
    
    def __init__(self):
        self.dashboard_templates = {}
        self.panel_id_counter = 1
        
        self.logger = logger.bind(component="dashboard_generator")
    
    def generate_main_dashboard(self) -> Dict[str, Any]:
        """Generate main monitoring dashboard"""
        dashboard = {
            "dashboard": {
                "id": None,
                "uid": "tml-mqtt-gateway-main",
                "title": "TML MQTT Gateway - Main Dashboard",
                "tags": ["tml", "mqtt", "gateway", "production"],
                "timezone": "browser",
                "schemaVersion": 30,
                "version": 1,
                "refresh": "5s",
                "time": {
                    "from": "now-1h",
                    "to": "now"
                },
                "panels": []
            }
        }
        
        # System Overview Row
        dashboard["dashboard"]["panels"].append(
            self._create_row_panel("System Overview", 0)
        )
        
        # Health Score
        dashboard["dashboard"]["panels"].append(
            self._create_gauge_panel(
                title="Health Score",
                metric="gateway_health_score",
                x=0, y=1, w=6, h=8,
                thresholds=[
                    {"value": 0, "color": "red"},
                    {"value": 70, "color": "yellow"},
                    {"value": 90, "color": "green"}
                ]
            )
        )
        
        # Active Connections
        dashboard["dashboard"]["panels"].append(
            self._create_stat_panel(
                title="Active Connections",
                metric="gateway_active_connections",
                x=6, y=1, w=6, h=4
            )
        )
        
        # Message Throughput
        dashboard["dashboard"]["panels"].append(
            self._create_stat_panel(
                title="Throughput (msg/s)",
                metric="gateway_message_throughput_per_second",
                x=12, y=1, w=6, h=4,
                unit="msg/s"
            )
        )
        
        # Error Rate
        dashboard["dashboard"]["panels"].append(
            self._create_gauge_panel(
                title="Error Rate",
                metric="gateway_error_rate_percent",
                x=18, y=1, w=6, h=8,
                unit="percent",
                thresholds=[
                    {"value": 0, "color": "green"},
                    {"value": 5, "color": "yellow"},
                    {"value": 10, "color": "red"}
                ]
            )
        )
        
        # CPU Usage
        dashboard["dashboard"]["panels"].append(
            self._create_timeseries_panel(
                title="CPU Usage",
                metrics=["gateway_system_cpu_percent"],
                x=6, y=5, w=6, h=4,
                unit="percent"
            )
        )
        
        # Memory Usage
        dashboard["dashboard"]["panels"].append(
            self._create_timeseries_panel(
                title="Memory Usage",
                metrics=["gateway_system_memory_percent"],
                x=12, y=5, w=6, h=4,
                unit="percent"
            )
        )
        
        # Performance Metrics Row
        dashboard["dashboard"]["panels"].append(
            self._create_row_panel("Performance Metrics", 9)
        )
        
        # Message Processing Time
        dashboard["dashboard"]["panels"].append(
            self._create_timeseries_panel(
                title="Message Processing Time",
                metrics=["gateway_message_processing_seconds"],
                x=0, y=10, w=12, h=8,
                unit="s",
                legend_format="{{le}}"
            )
        )
        
        # MQTT Metrics
        dashboard["dashboard"]["panels"].append(
            self._create_timeseries_panel(
                title="MQTT Messages",
                metrics=[
                    "mqtt_messages_received_total",
                    "mqtt_messages_published_total"
                ],
                x=12, y=10, w=12, h=8,
                legend_format="{{__name__}}"
            )
        )
        
        # Device Metrics Row
        dashboard["dashboard"]["panels"].append(
            self._create_row_panel("Device Metrics", 18)
        )
        
        # Online Devices
        dashboard["dashboard"]["panels"].append(
            self._create_stat_panel(
                title="Online Devices",
                metric="mqtt_connected_clients",
                x=0, y=19, w=6, h=4
            )
        )
        
        # Total Devices
        dashboard["dashboard"]["panels"].append(
            self._create_stat_panel(
                title="Total Devices",
                metric="db_device_count",
                x=6, y=19, w=6, h=4
            )
        )
        
        # Device Provisioning Rate
        dashboard["dashboard"]["panels"].append(
            self._create_timeseries_panel(
                title="Device Provisioning",
                metrics=["device_provisioning_total"],
                x=12, y=19, w=12, h=4
            )
        )
        
        # Kafka Metrics Row
        dashboard["dashboard"]["panels"].append(
            self._create_row_panel("Kafka Integration", 23)
        )
        
        # Kafka Messages
        dashboard["dashboard"]["panels"].append(
            self._create_timeseries_panel(
                title="Kafka Messages",
                metrics=[
                    "kafka_messages_sent_total",
                    "kafka_send_errors_total"
                ],
                x=0, y=24, w=12, h=6
            )
        )
        
        # Kafka Lag
        dashboard["dashboard"]["panels"].append(
            self._create_timeseries_panel(
                title="Kafka Producer Lag",
                metrics=["kafka_producer_lag_seconds"],
                x=12, y=24, w=12, h=6,
                unit="s"
            )
        )
        
        return dashboard
    
    def generate_device_dashboard(self) -> Dict[str, Any]:
        """Generate device-specific dashboard"""
        dashboard = {
            "dashboard": {
                "id": None,
                "uid": "tml-mqtt-gateway-devices",
                "title": "TML MQTT Gateway - Device Management",
                "tags": ["tml", "mqtt", "devices"],
                "timezone": "browser",
                "schemaVersion": 30,
                "version": 1,
                "refresh": "10s",
                "panels": []
            }
        }
        
        # Device Overview
        dashboard["dashboard"]["panels"].append(
            self._create_row_panel("Device Overview", 0)
        )
        
        # Device Status Table
        dashboard["dashboard"]["panels"].append(
            self._create_table_panel(
                title="Device Status",
                query="""
                    SELECT
                        device_id,
                        device_type,
                        status,
                        last_seen,
                        message_count,
                        error_count
                    FROM devices
                    WHERE last_seen > NOW() - INTERVAL '1 hour'
                    ORDER BY last_seen DESC
                """,
                x=0, y=1, w=24, h=10
            )
        )
        
        # Device Types Distribution
        dashboard["dashboard"]["panels"].append(
            self._create_piechart_panel(
                title="Device Types",
                query="""
                    SELECT
                        device_type,
                        COUNT(*) as count
                    FROM devices
                    GROUP BY device_type
                """,
                x=0, y=11, w=8, h=8
            )
        )
        
        # Device Status Distribution
        dashboard["dashboard"]["panels"].append(
            self._create_piechart_panel(
                title="Device Status",
                query="""
                    SELECT
                        status,
                        COUNT(*) as count
                    FROM devices
                    GROUP BY status
                """,
                x=8, y=11, w=8, h=8
            )
        )
        
        # Device Activity Heatmap
        dashboard["dashboard"]["panels"].append(
            self._create_heatmap_panel(
                title="Device Activity",
                metric="device_message_rate",
                x=16, y=11, w=8, h=8
            )
        )
        
        return dashboard
    
    def generate_security_dashboard(self) -> Dict[str, Any]:
        """Generate security monitoring dashboard"""
        dashboard = {
            "dashboard": {
                "id": None,
                "uid": "tml-mqtt-gateway-security",
                "title": "TML MQTT Gateway - Security",
                "tags": ["tml", "mqtt", "security"],
                "timezone": "browser",
                "schemaVersion": 30,
                "version": 1,
                "refresh": "30s",
                "panels": []
            }
        }
        
        # Security Overview
        dashboard["dashboard"]["panels"].append(
            self._create_row_panel("Security Overview", 0)
        )
        
        # Authentication Attempts
        dashboard["dashboard"]["panels"].append(
            self._create_timeseries_panel(
                title="Authentication Attempts",
                metrics=[
                    "auth_attempts_total",
                    "auth_failures_total"
                ],
                x=0, y=1, w=12, h=6
            )
        )
        
        # Certificate Status
        dashboard["dashboard"]["panels"].append(
            self._create_stat_panel(
                title="Active Certificates",
                metric="certificates_active_total",
                x=12, y=1, w=6, h=3
            )
        )
        
        # Certificates Expiring Soon
        dashboard["dashboard"]["panels"].append(
            self._create_stat_panel(
                title="Certificates Expiring",
                metric="certificates_expiring_soon",
                x=18, y=1, w=6, h=3
            )
        )
        
        # Encrypted Messages
        dashboard["dashboard"]["panels"].append(
            self._create_timeseries_panel(
                title="Encrypted Messages",
                metrics=["messages_encrypted_total"],
                x=12, y=4, w=12, h=3
            )
        )
        
        # Failed Auth by Method
        dashboard["dashboard"]["panels"].append(
            self._create_bargraph_panel(
                title="Failed Auth by Method",
                query="""
                    SELECT
                        auth_method,
                        COUNT(*) as failures
                    FROM auth_logs
                    WHERE success = false
                        AND timestamp > NOW() - INTERVAL '1 hour'
                    GROUP BY auth_method
                """,
                x=0, y=7, w=12, h=6
            )
        )
        
        # Locked Devices
        dashboard["dashboard"]["panels"].append(
            self._create_table_panel(
                title="Locked Devices",
                query="""
                    SELECT
                        device_id,
                        lock_reason,
                        locked_at,
                        unlock_at
                    FROM device_locks
                    WHERE unlock_at > NOW()
                """,
                x=12, y=7, w=12, h=6
            )
        )
        
        return dashboard
    
    def generate_edge_ml_dashboard(self) -> Dict[str, Any]:
        """Generate Edge ML monitoring dashboard"""
        dashboard = {
            "dashboard": {
                "id": None,
                "uid": "tml-mqtt-gateway-edge-ml",
                "title": "TML MQTT Gateway - Edge ML",
                "tags": ["tml", "mqtt", "edge", "ml"],
                "timezone": "browser",
                "schemaVersion": 30,
                "version": 1,
                "refresh": "10s",
                "panels": []
            }
        }
        
        # Model Overview
        dashboard["dashboard"]["panels"].append(
            self._create_row_panel("Edge ML Models", 0)
        )
        
        # Deployed Models
        dashboard["dashboard"]["panels"].append(
            self._create_stat_panel(
                title="Deployed Models",
                metric="edge_models_deployed",
                x=0, y=1, w=6, h=4
            )
        )
        
        # Total Inferences
        dashboard["dashboard"]["panels"].append(
            self._create_stat_panel(
                title="Total Inferences",
                metric="edge_inferences_total",
                x=6, y=1, w=6, h=4
            )
        )
        
        # Inference Rate
        dashboard["dashboard"]["panels"].append(
            self._create_timeseries_panel(
                title="Inference Rate",
                metrics=["edge_inference_rate_per_second"],
                x=12, y=1, w=12, h=4,
                unit="ops"
            )
        )
        
        # Inference Latency
        dashboard["dashboard"]["panels"].append(
            self._create_timeseries_panel(
                title="Inference Latency",
                metrics=["edge_inference_latency_ms"],
                x=0, y=5, w=12, h=6,
                unit="ms"
            )
        )
        
        # Model Accuracy
        dashboard["dashboard"]["panels"].append(
            self._create_timeseries_panel(
                title="Model Accuracy",
                metrics=["edge_model_accuracy"],
                x=12, y=5, w=12, h=6,
                unit="percentunit"
            )
        )
        
        # Model Status Table
        dashboard["dashboard"]["panels"].append(
            self._create_table_panel(
                title="Model Status",
                query="""
                    SELECT
                        model_id,
                        model_type,
                        version,
                        status,
                        inference_count,
                        avg_latency_ms,
                        last_inference
                    FROM edge_models
                    ORDER BY last_inference DESC
                """,
                x=0, y=11, w=24, h=8
            )
        )
        
        return dashboard
    
    def _create_row_panel(self, title: str, y_pos: int) -> Dict[str, Any]:
        """Create a row panel"""
        panel = {
            "id": self._get_next_panel_id(),
            "type": "row",
            "title": title,
            "collapsed": False,
            "gridPos": {"h": 1, "w": 24, "x": 0, "y": y_pos}
        }
        return panel
    
    def _create_gauge_panel(
        self,
        title: str,
        metric: str,
        x: int, y: int, w: int, h: int,
        unit: str = "none",
        thresholds: List[Dict] = None
    ) -> Dict[str, Any]:
        """Create a gauge panel"""
        panel = {
            "id": self._get_next_panel_id(),
            "type": "gauge",
            "title": title,
            "gridPos": {"h": h, "w": w, "x": x, "y": y},
            "targets": [{
                "expr": metric,
                "refId": "A"
            }],
            "options": {
                "orientation": "auto",
                "showThresholdLabels": False,
                "showThresholdMarkers": True
            },
            "fieldConfig": {
                "defaults": {
                    "unit": unit,
                    "thresholds": {
                        "mode": "absolute",
                        "steps": thresholds or [
                            {"value": 0, "color": "green"},
                            {"value": 80, "color": "red"}
                        ]
                    }
                }
            }
        }
        return panel
    
    def _create_stat_panel(
        self,
        title: str,
        metric: str,
        x: int, y: int, w: int, h: int,
        unit: str = "none"
    ) -> Dict[str, Any]:
        """Create a stat panel"""
        panel = {
            "id": self._get_next_panel_id(),
            "type": "stat",
            "title": title,
            "gridPos": {"h": h, "w": w, "x": x, "y": y},
            "targets": [{
                "expr": metric,
                "refId": "A"
            }],
            "fieldConfig": {
                "defaults": {
                    "unit": unit
                }
            }
        }
        return panel
    
    def _create_timeseries_panel(
        self,
        title: str,
        metrics: List[str],
        x: int, y: int, w: int, h: int,
        unit: str = "none",
        legend_format: str = "{{__name__}}"
    ) -> Dict[str, Any]:
        """Create a time series panel"""
        targets = []
        for i, metric in enumerate(metrics):
            targets.append({
                "expr": metric,
                "legendFormat": legend_format,
                "refId": chr(65 + i)  # A, B, C...
            })
        
        panel = {
            "id": self._get_next_panel_id(),
            "type": "timeseries",
            "title": title,
            "gridPos": {"h": h, "w": w, "x": x, "y": y},
            "targets": targets,
            "fieldConfig": {
                "defaults": {
                    "unit": unit,
                    "custom": {
                        "lineInterpolation": "linear",
                        "lineWidth": 1,
                        "fillOpacity": 10,
                        "gradientMode": "none",
                        "spanNulls": False,
                        "showPoints": "never"
                    }
                }
            },
            "options": {
                "legend": {
                    "displayMode": "list",
                    "placement": "bottom"
                },
                "tooltip": {
                    "mode": "single"
                }
            }
        }
        return panel
    
    def _create_table_panel(
        self,
        title: str,
        query: str,
        x: int, y: int, w: int, h: int
    ) -> Dict[str, Any]:
        """Create a table panel"""
        panel = {
            "id": self._get_next_panel_id(),
            "type": "table",
            "title": title,
            "gridPos": {"h": h, "w": w, "x": x, "y": y},
            "targets": [{
                "rawSql": query,
                "format": "table",
                "refId": "A"
            }],
            "options": {
                "showHeader": True
            }
        }
        return panel
    
    def _create_piechart_panel(
        self,
        title: str,
        query: str,
        x: int, y: int, w: int, h: int
    ) -> Dict[str, Any]:
        """Create a pie chart panel"""
        panel = {
            "id": self._get_next_panel_id(),
            "type": "piechart",
            "title": title,
            "gridPos": {"h": h, "w": w, "x": x, "y": y},
            "targets": [{
                "rawSql": query,
                "format": "table",
                "refId": "A"
            }],
            "options": {
                "pieType": "donut",
                "displayLabels": ["name", "percent"],
                "legendDisplayMode": "list",
                "legendPlacement": "right"
            }
        }
        return panel
    
    def _create_heatmap_panel(
        self,
        title: str,
        metric: str,
        x: int, y: int, w: int, h: int
    ) -> Dict[str, Any]:
        """Create a heatmap panel"""
        panel = {
            "id": self._get_next_panel_id(),
            "type": "heatmap",
            "title": title,
            "gridPos": {"h": h, "w": w, "x": x, "y": y},
            "targets": [{
                "expr": f"histogram_quantile(0.95, sum(rate({metric}[5m])) by (le))",
                "format": "heatmap",
                "refId": "A"
            }],
            "options": {
                "calculate": False,
                "cellGap": 2,
                "color": {
                    "scheme": "Spectral"
                }
            }
        }
        return panel
    
    def _create_bargraph_panel(
        self,
        title: str,
        query: str,
        x: int, y: int, w: int, h: int
    ) -> Dict[str, Any]:
        """Create a bar graph panel"""
        panel = {
            "id": self._get_next_panel_id(),
            "type": "bargauge",
            "title": title,
            "gridPos": {"h": h, "w": w, "x": x, "y": y},
            "targets": [{
                "rawSql": query,
                "format": "table",
                "refId": "A"
            }],
            "options": {
                "orientation": "horizontal",
                "displayMode": "gradient",
                "showUnfilled": True
            }
        }
        return panel
    
    def _get_next_panel_id(self) -> int:
        """Get next panel ID"""
        panel_id = self.panel_id_counter
        self.panel_id_counter += 1
        return panel_id
    
    def export_dashboard(self, dashboard: Dict[str, Any], filename: str) -> None:
        """Export dashboard to JSON file"""
        try:
            with open(filename, 'w') as f:
                json.dump(dashboard, f, indent=2)
            
            self.logger.info("Dashboard exported", filename=filename)
            
        except Exception as e:
            self.logger.error("Failed to export dashboard",
                            filename=filename,
                            error=str(e))
    
    def generate_all_dashboards(self) -> List[Dict[str, Any]]:
        """Generate all dashboards"""
        dashboards = []
        
        # Generate main dashboard
        dashboards.append(self.generate_main_dashboard())
        
        # Generate device dashboard
        dashboards.append(self.generate_device_dashboard())
        
        # Generate security dashboard
        dashboards.append(self.generate_security_dashboard())
        
        # Generate Edge ML dashboard
        dashboards.append(self.generate_edge_ml_dashboard())
        
        return dashboards
