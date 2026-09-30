"""
LibreHardwareMonitor REST API client.
Fetches sensor data (fans, temperatures, voltages) from LHM running on localhost.
"""
import requests
import logging
from typing import Dict, Any, List


class LHMClient:
    def __init__(self, url: str = "http://localhost:8085/data.json", timeout: int = 2):
        self.url = url
        self.timeout = timeout
        self.available = self._check_availability()

    def _check_availability(self) -> bool:
        """Check if LibreHardwareMonitor is running and accessible."""
        try:
            response = requests.get(self.url, timeout=self.timeout)
            return response.status_code == 200
        except Exception as e:
            logging.warning(f"LibreHardwareMonitor not available at {self.url}: {e}")
            return False

    def _walk_sensors(self, nodes: List[Dict], sensors: Dict[str, Any], prefix: str = ""):
        """Recursively walk the sensor tree and extract values."""
        for node in nodes:
            # Process children recursively
            if node.get("Children"):
                # Use the node's text as prefix for better organization
                node_text = node.get("Text", "")
                new_prefix = f"{prefix}{node_text}_" if node_text else prefix
                self._walk_sensors(node["Children"], sensors, new_prefix)

            # Extract sensor values
            sensor_type = node.get("Type", "")
            text = node.get("Text", "")
            value = node.get("Value", "")

            # Only process nodes with actual values
            if value and value != "-":
                # Clean up the key name
                key = f"{prefix}{text}".replace(" ", "_").replace("/", "_").lower()

                # Parse the value based on type
                try:
                    # Remove units from value string
                    clean_value = value.replace(" °C", "").replace(" RPM", "").replace(" V", "")
                    clean_value = clean_value.replace(" W", "").replace(" %", "").replace(" MHz", "")

                    # Try to convert to float
                    if clean_value:
                        sensors[key] = float(clean_value)
                except ValueError:
                    # If conversion fails, store as string
                    sensors[key] = value

    def get_sensors(self) -> Dict[str, Any]:
        """Get all sensor data from LibreHardwareMonitor."""
        if not self.available:
            self.available = self._check_availability()

        if not self.available:
            return {
                "lhm_available": False,
            }

        try:
            response = requests.get(self.url, timeout=self.timeout)
            response.raise_for_status()
            data = response.json()

            sensors = {"lhm_available": True}

            # Walk the sensor tree
            if "Children" in data:
                self._walk_sensors(data["Children"], sensors)

            return sensors

        except Exception as e:
            logging.error(f"Failed to fetch LibreHardwareMonitor data: {e}")
            return {
                "lhm_available": False,
                "lhm_error": str(e),
            }

    def get_specific_sensors(self, sensor_names: List[str]) -> Dict[str, Any]:
        """Get specific sensors by name (case-insensitive partial match)."""
        all_sensors = self.get_sensors()

        if not all_sensors.get("lhm_available", False):
            return all_sensors

        filtered = {"lhm_available": True}

        # Filter sensors based on requested names
        for key, value in all_sensors.items():
            if key == "lhm_available":
                continue

            for name in sensor_names:
                if name.lower() in key.lower():
                    filtered[key] = value
                    break

        return filtered

    def get_fans(self) -> Dict[str, Any]:
        """Get all fan speed sensors."""
        return self.get_specific_sensors(["fan"])

    def get_temperatures(self) -> Dict[str, Any]:
        """Get all temperature sensors."""
        return self.get_specific_sensors(["temperature", "temp"])

    def get_voltages(self) -> Dict[str, Any]:
        """Get all voltage sensors."""
        return self.get_specific_sensors(["voltage", "volt"])
