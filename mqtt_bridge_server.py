import json
import math
import os
import sys
import paho.mqtt.client as mqtt
from paho.mqtt.client import MQTTMessage
from pymongo import MongoClient
from pymongo.server_api import ServerApi
from pymongo.errors import ConnectionFailure 

from ros_data import ros_data_t
import rclpy
from rclpy.node import Node
import threading
import time


# ---------------------- SECURE EXECUTION ----------------------
def enforce_shell_parent():
    if os.getenv("LAUNCHED_VIA_SETUP") != "1":
        error_msg = """
        \033[1;91m
        PROTECTED EXECUTION !

        The script 'mqtt_bridge_server.py' must be launched via:

            sh auto_server_setup.sh

        Direct execution is disabled to avoid data loss.
        \033[0m
        """
        print(error_msg, file=sys.stderr)
        sys.exit(1)
enforce_shell_parent()
# -------------------------------------------------------------


# MQTT Settings
MQTT_DEFAULT_HOST = "localhost"
MQTT_DEFAULT_PORT = 1883
MQTT_DEFAULT_TIMEOUT = 120

JSON_GLOBAL_TOPIC = "global/json"
MQTT_GLOBAL_TOPIC = "mqtt/global"


"""
SERVERSIDE - THIS SCRIPT MUST BE EXECUTED ON THE SERVER!!!

This script subscribes to MQTT topics, collects messages,
stores them in MongoDB, and republishes them for Telegraf/InfluxDB.
"""


class mqtt_data_uploader_t(Node):
    def __init__(self, host=MQTT_DEFAULT_HOST, port=MQTT_DEFAULT_PORT):
        super().__init__('ros2_mqtt_publisher')

        self.ros_data = ros_data_t()
        self.mqtt_client_server = mqtt.Client()
        # timestamp of last received MQTT message (seconds since epoch)
        self.last_msg_time = 0

        try:
            # ---------------------- MONGO CONNECTION ----------------------
            self.get_logger().info("Trying to connect to MongoDB [...]")

            # Prefer MONGO_URI env var, otherwise use the requested DB URI
            # default to the provided remote MongoDB with credentials
            mongo_uri = os.getenv("MONGO_URI", "mongodb://admin:cdei2025@147.83.52.40:27017/")
            # Create client (no ServerApi enforced to avoid compatibility issues)
            self.client = MongoClient(mongo_uri, serverSelectionTimeoutMS=10000)
            # Test connection
            self.client.admin.command('ping')
            self.get_logger().info(f"Connected to MongoDB at {mongo_uri}")
            # Access the target database and collection
            # use the same collection as before ("Test") to keep historic format
            self.mongo_db_collection = self.client["ROS2"]["Alex Test"]
            # --------------------------------------------------------------

            # ---------------------- MQTT CONNECTION ----------------------
            #            self.mqtt_client_server.connect(MQTT_DEFAULT_HOST, MQTT_DEFAULT_PORT, MQTT_DEFAULT_TIMEOUT)
            #            self.get_logger().info("Connected to MQTT broker.")
            # Use the host/port passed to the constructor (was hardcoded to MQTT_DEFAULT_HOST)
            self.mqtt_client_server.connect(host, port, MQTT_DEFAULT_TIMEOUT)
            self.get_logger().info(f"Connected to MQTT broker at {host}:{port}.")
            self.subscribe_to_topics()
            # --------------------------------------------------------------

            # Background thread for continuous data publishing
            threading.Thread(target=self.robot_message_01, daemon=True).start()

        except ConnectionFailure as cf:
            self.get_logger().error(f"Failed to connect to MongoDB: {cf}")

        except Exception as me:
            self.get_logger().error(f"Failed to connect to MQTT broker: {me}")

        # Start MQTT listener loop
        self.mqtt_client_server.loop_start()


    def subscribe_to_topics(self) -> None:
        self.mqtt_client_server.subscribe(MQTT_GLOBAL_TOPIC, qos=0)
        self.get_logger().info("Subscribed to MQTT global topic.")
        self.mqtt_client_server.on_message = self.on_mqtt_message


    def on_mqtt_message(self, client, userdata, msg: MQTTMessage):
        """Callback when a message is received from MQTT."""
        try:
            payload = json.loads(msg.payload.decode("utf-8"))
            print(f"[DEBUG] MQTT Received raw: {payload}")

            # mark last message time so publisher knows new data arrived
            self.last_msg_time = time.time()
            self.ros_data._is_data_available = True
            self.ros_data.update(payload)

        except Exception as e:
            self.get_logger().error(f"Error processing MQTT message: {e}")


    def publish(self, topic: str, data: dict) -> None:
        """Publish data to MQTT and store it in MongoDB."""
        if data:
            try:
                payload = json.dumps(data, indent=4)

                # Publish to MQTT for InfluxDB via Telegraf
                self.mqtt_client_server.publish(topic, payload)

                # Store raw JSON into MongoDB
                self.mongo_db_collection.insert_one(data)

                self.get_logger().info(f"Published to MQTT ({topic}) and stored in MongoDB.")
            except Exception as e:
                self.get_logger().error(f"Publish or MongoDB insert failed: {e}")


    # def secure_data_handler(self):
    #     """Wait until ROS data becomes available."""
    #     once = True
    #     while not self.ros_data.is_data_available():
    #         if once:
    #             self.get_logger().info("Data not available yet, waiting [...]")
    #             once = False
    #     self.get_logger().info("Data available, proceeding [...]")
    #     return self.ros_data


    def robot_message_01(self):
        """Main loop to aggregate and publish sensor data."""
        rd_handler = self.ros_data 

        def manage_data(sample, samples: list):
            if sample is None:
                return
            if isinstance(sample, float) and math.isnan(sample):
                return
            if sample not in samples:
                samples.append(sample)

        sampling_duration_sec = 0.5  # seconds per batch

        while True:
            canopy_temperature_samples = []
            ndvi_samples = []
            ndvi_3d_samples = []
            ndvi_ir_samples = []
            ndvi_visible_samples = []
            area_samples = []
            location_samples = []
            biomass_samples = []
            crop_light_state_samples = []
            crop_type_samples = []
            ambient_temperature_samples = []
            relative_humidity_samples = []
            absolute_humidity_samples = []
            dew_point_samples = []
            utm_baselink_X_samples = []
            utm_baselink_Y_samples = []
            utm_baselink_Z_samples = []

            start_time = time.time()
 
            while (time.time() - start_time) <= sampling_duration_sec:
                # Flatten plant lists into a single array of objects (deduplicate/update by 'id')
                if rd_handler.t_plants and isinstance(rd_handler.t_plants, list):
                    # collect existing ids to avoid duplicates
                    existing_ids = {p.get('id') for p in canopy_temperature_samples if isinstance(p, dict) and p.get('id') is not None}
                    for plant in rd_handler.t_plants:
                        if plant is None:
                            continue
                        if isinstance(plant, dict):
                            pid = plant.get('id')
                            if pid is not None:
                                if pid in existing_ids:
                                    # update existing entry with latest fields
                                    for ex in canopy_temperature_samples:
                                        if isinstance(ex, dict) and ex.get('id') == pid:
                                            ex.update(plant)
                                            break
                                else:
                                    canopy_temperature_samples.append(plant.copy())
                                    existing_ids.add(pid)
                            else:
                                # no id: append if not already present
                                if plant not in canopy_temperature_samples:
                                    canopy_temperature_samples.append(plant.copy())
                        else:
                            # non-dict plant entry: keep uniqueness
                            if plant not in canopy_temperature_samples:
                                canopy_temperature_samples.append(plant)
                else:
                    # fallback for older flat-format messages (single float)
                    manage_data(rd_handler.t_canopy_temperature, canopy_temperature_samples)
                manage_data(rd_handler.n_ndvi, ndvi_samples)
                manage_data(rd_handler.n_ndvi_3d, ndvi_3d_samples)
                manage_data(rd_handler.n_ir, ndvi_ir_samples)
                manage_data(rd_handler.n_visible, ndvi_visible_samples)
                manage_data(rd_handler.n_area, area_samples)
                manage_data(rd_handler.n_location, location_samples)
                manage_data(rd_handler.n_biomass, biomass_samples)
                manage_data(rd_handler.n_crop_light_state, crop_light_state_samples)
                manage_data(rd_handler.n_crop_type, crop_type_samples)
                manage_data(rd_handler.n_ambient_temperature, ambient_temperature_samples)
                manage_data(rd_handler.n_relative_humidity, relative_humidity_samples)
                manage_data(rd_handler.n_absolute_humidity, absolute_humidity_samples)
                manage_data(rd_handler.n_dew_point, dew_point_samples)
                manage_data(rd_handler.tf_x, utm_baselink_X_samples)
                manage_data(rd_handler.tf_y, utm_baselink_Y_samples)
                manage_data(rd_handler.tf_z, utm_baselink_Z_samples)

            # JSON structure to store
            json_data = {
                "timestamp": rd_handler.g_timestamp,
                "latitude": rd_handler.g_latitude,
                "longitude": rd_handler.g_longitude,
                "altitude": rd_handler.g_altitude,
                "status": rd_handler.g_status,
                "service": rd_handler.g_service,

                "canopy_temperature_data": canopy_temperature_samples,
                "t_entity_count": rd_handler.t_entity_count,
                "ndvi_data": ndvi_samples,
                "ndvi_3d_data": ndvi_3d_samples,
                "ndvi_ir_data": ndvi_ir_samples,
                "ndvi_visible_data": ndvi_visible_samples,

                "area_data": area_samples,
                "location_data": location_samples,
                "biomass_data": biomass_samples,
                "crop_light_state_data": crop_light_state_samples,
                "crop_type_data": crop_type_samples,

                "ambient_temperature_data": ambient_temperature_samples,
                "relative_humidity_data": relative_humidity_samples,
                "absolute_humidity_data": absolute_humidity_samples,
                "dew_point_data": dew_point_samples,

                "utm_baselink_X": utm_baselink_X_samples,
                "utm_baselink_Y": utm_baselink_Y_samples,
                "utm_baselink_Z": utm_baselink_Z_samples,
            }

            # Only publish if there is actual data collected
            all_samples = [
                canopy_temperature_samples, ndvi_samples, ndvi_3d_samples, ndvi_ir_samples,
                ndvi_visible_samples, area_samples, location_samples, biomass_samples,
                crop_light_state_samples, crop_type_samples, ambient_temperature_samples,
                relative_humidity_samples, absolute_humidity_samples, dew_point_samples,
                utm_baselink_X_samples, utm_baselink_Y_samples, utm_baselink_Z_samples
            ]
            # Publish only if at least one message arrived during the sampling window
            # (prevents re-publishing the last-known values when sender stopped)
            if self.last_msg_time >= start_time and any(samples for samples in all_samples):
                # Publish to both MQTT and MongoDB
                self.publish(JSON_GLOBAL_TOPIC, json_data)
            else:
                # no new messages in this sampling window -> skip publishing
                self.get_logger().debug("No new MQTT data in sampling window; skipping publish.")


def main(args=None):
    rclpy.init(args=args)
    node = mqtt_data_uploader_t()

    try:
        rclpy.spin(node)
    except KeyboardInterrupt:
        pass
    finally:
        node.mqtt_client_server.disconnect()
        node.get_logger().info("Disconnected from MQTT broker.")
        node.destroy_node()
        rclpy.shutdown()


if __name__ == '__main__':
    main()

