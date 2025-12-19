from dataclasses import dataclass
    
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
    n_location: str = None
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


    def update(self, data: dict):
        msg: str = data.get("msg_type")
        
        if not msg:
            print(f"[WARN] Skipping message without msg_type: {data}")
            return
        
        try:
            if "gps" in msg:
                self.g_timestamp = data.get("timestamp")
                self.g_latitude = data.get("latitude")
                self.g_longitude = data.get("longitude")
                self.g_altitude = data.get("altitude")
                self.g_status = data.get("status")
                self.g_service = data.get("service")

            elif "temperature" in msg:
                plants = data.get("plants", [])
                if plants:
                    # Compute average canopy_temperature and cwsi
                    self.t_entity_count = len(plants)
                    self.t_canopy_temperature = sum(p["canopy_temperature"] for p in plants) / len(plants)
                    self.t_cswi = sum(p["cwsi"] for p in plants) / len(plants)
                else:
                    # Fallback if no plants list
                    self.t_entity_count = data.get("entity_count")
                    self.t_canopy_temperature = data.get("canopy_temperature")
                    self.t_cswi = data.get("cwsi")


            elif "ndvi" in msg:
                self.n_ndvi = data.get("ndvi")
                self.n_ndvi_3d = data.get("ndvi_3d")
                self.n_ir = data.get("ir")
                self.n_visible = data.get("visible")

            elif "area" in msg:
                self.n_area = data.get("area")

            elif "location" in msg:
                self.n_location = data.get("location")

            elif "biomass" in msg:
                self.n_biomass = data.get("biomass")

            elif "light_state" in msg:
                self.n_crop_light_state = data.get("light_state") 

            elif "crop_type" in msg:
                self.n_crop_type = data.get("crop_type") 

            elif "ambient_temperature" in msg:
                # Accept a few possible key names and coerce to float when possible
                val = None
                if "ambient_temperature" in data:
                    val = data.get("ambient_temperature")
                elif "ambientTemp" in data:
                    val = data.get("ambientTemp")
                elif "ambient" in data:
                    val = data.get("ambient")
                if val is not None:
                    try:
                        self.n_ambient_temperature = float(val)
                    except Exception:
                        # keep raw value if cannot coerce, but log for debugging
                        print(f"[WARN] ambient temperature not float: {val}")
                        self.n_ambient_temperature = val

            elif "relative_humidity" in msg:
                self.n_relative_humidity = data.get("relative_humidity") 

            elif "absolute_humidity" in msg:
                self.n_absolute_humidity = data.get("absolute_humidity") 

            elif "dew_point" in msg:
                self.n_dew_point = data.get("dew_point") 

            elif "tf_position" in msg:
                # UTM baselink tf position (x,y,z)
                # Accept either x,y,z or point sub-dict
                if "x" in data and "y" in data and "z" in data:
                    try:
                        self.tf_x = float(data.get("x"))
                        self.tf_y = float(data.get("y"))
                        self.tf_z = float(data.get("z"))
                    except Exception:
                        # keep raw values if conversion fails
                        self.tf_x = data.get("x")
                        self.tf_y = data.get("y")
                        self.tf_z = data.get("z")
                elif "point" in data and isinstance(data["point"], dict):
                    p = data["point"]
                    try:
                        self.tf_x = float(p.get("x"))
                        self.tf_y = float(p.get("y"))
                        self.tf_z = float(p.get("z"))
                    except Exception:
                        self.tf_x = p.get("x")
                        self.tf_y = p.get("y")
                        self.tf_z = p.get("z")

            else:
                print(f"[WARN] Unsupported msg_type, storing raw payload: {data}")
        
            # mark data available for your publishing loop
            self._is_data_available = True

        except Exception as e:
            print(f"[ERROR] Error processing MQTT message: {e}")

        
    def is_data_available(self) -> bool:
        return self._is_data_available