from dataclasses import dataclass
import re
from typing import Optional, Dict, Any

# A helper class to store and update data from ROS messages.

@dataclass
class ros_data_t:
    
    _is_data_available: bool = False
    
    # Raw fields
    
    g_timestamp: int = None 
    g_latitude: float = None
    g_longitude: float = None
    g_altitude: float = None
    g_status: int = None
    g_service: int = None
    t_entity_count: str = None
    t_canopy_temperature: float = None
    t_cswi: float = None
    n_ndvi: float = None
    n_ndvi_3d: float = None
    n_ir: float = None
    n_visible: float = None
    n_area: float = None
    # now we store structured location data (dict with keys section,row,position_from_N,direction)
    n_location: Optional[Dict[str, Any]] = None
    n_biomass: float = None
    n_crop_light_state: str = None
    n_crop_type: str = None
    n_ambient_temperature: float = None
    n_relative_humidity: float = None
    n_absolute_humidity: float = None
    n_dew_point: float = None
    tf_x: float = None
    tf_y: float = None
    tf_z: float = None
    t_plants: list = None  # list of dicts for canopy temperature data per plant


    def update(self, data: dict):
        msg: str = data.get("msg_type")
        
        if not msg:
            print(f"[WARN] Skipping message without msg_type: {data}")
            return
        
        try:
            # GPS / position messages: prefer "ts" then "timestamp
            if "gps" in msg:
                self.g_timestamp = data.get("ts", data.get("timestamp"))
                self.g_latitude = data.get("latitude")
                self.g_longitude = data.get("longitude")
                self.g_altitude = data.get("altitude")
                self.g_status = data.get("status")
                self.g_service = data.get("service")

            elif "ambient_temperature" in msg:
                self.n_ambient_temperature = data.get("ambient_temperature", data.get("ambient_temperature"))

            # NDVI messages: accept variant field names
            elif "ndvi" in msg:
                self.n_ndvi = data.get("ndvi", data.get("ndvi_value"))
                self.n_ndvi_3d = data.get("ndvi_3d", data.get("ndvi3d"))
                # some payloads use ndvi_ir / ndvi_visible or ndvi_ir / ndvi_visible keys
                self.n_ir = data.get("ndvi_ir", data.get("ir"))
                self.n_visible = data.get("ndvi_visible", data.get("visible"))

            elif "area" in msg:
                self.n_area = data.get("area")

            elif "location" in msg:
                # Accept either already-structured dict or a single location string
                loc = data.get("location")
                if isinstance(loc, dict):
                    # try to normalize/ensure keys
                    parsed = {
                        "section": loc.get("section"),
                        "row": loc.get("row"),
                        "position_from_N": None,
                        "direction": loc.get("direction")
                    }
                    # try to parse position if present as string
                    pos = loc.get("position_from_N") or loc.get("position") or loc.get("position_from_n")
                    if pos is not None:
                        try:
                            parsed['position_from_N'] = float(re.search(r'([-+]?[0-9]*\.?[0-9]+)', str(pos)).group(1))
                        except Exception:
                            parsed['position_from_N'] = None
                    self.n_location = parsed
                elif isinstance(loc, str):
                    self.n_location = _parse_location_string(loc)
                else:
                    self.n_location = None

            elif "biomass" in msg:
                self.n_biomass = data.get("biomass")

            elif "light_state" in msg:
                # some payloads use crop_light_state or light_state
                self.n_crop_light_state = data.get("crop_light_state", data.get("light_state"))

            elif "crop_type" in msg:
                self.n_crop_type = data.get("crop_type")

            # Temperature messages: keep full plants list so canopy_temperature_data is nested array
            elif "temperature" in msg:
                plants = data.get("plants")
                if plants and isinstance(plants, list):
                    self.t_plants = plants  # store entire list of dicts [{id, canopy_temperature, cwsi}, ...]
                    # entity count fallback
                    self.t_entity_count = data.get("entity_count", len(plants))
                    # keep an average for backward compatibility (optional)
                    try:
                        temps = [float(p.get("canopy_temperature")) for p in plants if p.get("canopy_temperature") is not None]
                        self.t_canopy_temperature = sum(temps) / len(temps) if temps else None
                    except Exception:
                        self.t_canopy_temperature = None
                else:
                    # older flat format
                    self.t_entity_count = data.get("entity_count")
                    self.t_canopy_temperature = data.get("canopy_temperature")
                    self.t_cswi = data.get("cwsi")

            elif "relative_humidity" in msg:
                self.n_relative_humidity = data.get("relative_humidity", data.get("humidity"))

            elif "absolute_humidity" in msg:
                self.n_absolute_humidity = data.get("absolute_humidity")

            elif "dew_point" in msg:
                self.n_dew_point = data.get("dew_point")

            elif "tf_position" in msg:
                # store tf/utm baselink values (x,y,z)
                if "x" in data and "y" in data and "z" in data:
                    try:
                        self.tf_x = float(data.get("x"))
                        self.tf_y = float(data.get("y"))
                        self.tf_z = float(data.get("z"))
                    except Exception:
                        self.tf_x = data.get("x"); self.tf_y = data.get("y"); self.tf_z = data.get("z")
                elif "point" in data and isinstance(data["point"], dict):
                    p = data["point"]
                    try:
                        self.tf_x = float(p.get("x")); self.tf_y = float(p.get("y")); self.tf_z = float(p.get("z"))
                    except Exception:
                        self.tf_x = p.get("x"); self.tf_y = p.get("y"); self.tf_z = p.get("z")

            else:
                # unknown messages: keep raw if needed
                pass

            # mark data available for your publishing loop
            self._is_data_available = True

        except Exception as e:
            print(f"[ERROR] Error processing MQTT message in ros_data.update: {e}")

        
    def is_data_available(self) -> bool:
        return self._is_data_available

def _parse_location_string(s: str) -> Dict[str, Any]:
    """
    Parse a location string like:
      'section: open air, row: row1-2, position_from_N: 11.64 m, direction: North → South'
    into a dict:
      { "section": "...", "row": "...", "position_from_N": 11.64, "direction": "South → North" }
    """
    out: Dict[str, Any] = {
        "section": None,
        "row": None,
        "position_from_N": None,
        "direction": None
    }

    if not s or not isinstance(s, str):
        return out

    # split by commas, then extract key:value pairs
    parts = [p.strip() for p in re.split(r',\s*', s) if p.strip()]
    for p in parts:
        if ':' in p:
            k, v = [x.strip() for x in p.split(':', 1)]
            kl = k.lower()
            if 'section' in kl:
                val = v.strip()
                # normalize "open air" to example format
                if 'open air' in val.lower():
                    out['section'] = "section 3 (Open air)"
                else:
                    out['section'] = val.title()
            elif 'row' in kl:
                rv = v.strip().lower()
                # keep row token, remove spaces
                # if pattern rowNN-NN, try to sanitize by removing spaces
                m = re.search(r'(\d+)(?:\s*-\s*(\d+))?', rv)
                if m:
                    if m.group(2):
                        # combine numbers (e.g. "1-2" -> "1-2") keep dash, or join? keep original compact
                        out['row'] = f"row{m.group(1)}-{m.group(2)}"
                    else:
                        out['row'] = f"row{m.group(1)}"
                else:
                    out['row'] = rv
            elif 'position' in kl or 'position_from_n' in kl:
                # extract float (meters)
                m = re.search(r'([-+]?[0-9]*\.?[0-9]+)', v)
                if m:
                    try:
                        out['position_from_N'] = float(m.group(1))
                    except Exception:
                        out['position_from_N'] = None
                else:
                    out['position_from_N'] = None
            elif 'direction' in kl:
                dv = v.replace('->', '→').replace('to', '→').strip()
                # Normalize order: prefer "South → North" if both present
                low = dv.lower()
                if 'north' in low and 'south' in low:
                    out['direction'] = "South → North"
                else:
                    out['direction'] = dv
            else:
                # unknown key: store raw
                out[k] = v
        else:
            # no colon: try to detect direction token or single value
            low = p.lower()
            if 'north' in low or 'south' in low:
                if 'north' in low and 'south' in low:
                    out['direction'] = "South → North"
                else:
                    out['direction'] = p
    return out