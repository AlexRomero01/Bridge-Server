This project implements a server-side MQTT subscriber and data aggregator that bridges ROS2 sensor topics with a MongoDB database. It subscribes to global MQTT topics, stores incoming messages, and republishes them for downstream services like Telegraf/InfluxDB.

Features
-Subscribes to MQTT topic mqtt/global (and global/json) from ROS2 publishers.
-Stores incoming JSON messages into MongoDB.
-Republishes data for analytics pipelines (Telegraf/InfluxDB compatible).
-ROS2 node integration for continuous data aggregation.
-Automatic deduplication and filtering of ROS2 sensor data.

Requirements:
-Ubuntu 22.04
-Python 3.10+
-ROS2 Humble
-MQTT broker (Mosquitto recommended)
-MongoDB (remote or local)
