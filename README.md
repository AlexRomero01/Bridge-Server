# Bridge Server

A data aggregation and bridging server that connects ROS2, MQTT, InfluxDB, and MongoDB to collect and serve agricultural sensor data.

## Overview

This project implements a server infrastructure for managing sensor data from IoT devices in an agricultural monitoring system. It bridges multiple technologies:

- **ROS2**: For robot operating system integration
- **MQTT**: Lightweight messaging protocol for device communication
- **InfluxDB**: Time-series database for metrics storage
- **MongoDB**: Document database for data persistence
- **FastAPI**: REST API for data querying and retrieval

## Architecture

### Core Components

1. **mqtt_bridge_server.py** - Main server application
   - Subscribes to MQTT topics
   - Collects and aggregates sensor messages
   - Stores data in MongoDB
   - Enforces secure execution via setup script

2. **fast_api_bridge.py** - REST API server
   - Provides HTTP endpoints for data queries
   - Integrates with InfluxDB for time-series queries
   - ROS2 node integration
   - Configurable data limitations (default: 10 records)

3. **ros_data.py** - Data model
   - Dataclass for ROS message data
   - Supports multiple sensor types:
     - GPS/Location data (timestamp, latitude, longitude, altitude, status)
     - Thermal sensors (canopy temperature, ambient temperature)
     - Spectral sensors (NDVI, IR, visible light)
     - Environmental data (humidity, dew point)
     - Transform data (3D coordinates)
     - Plant-specific metrics (biomass, crop type, light state)

4. **auto_server_setup.sh** - Automated initialization script
   - Kills existing processes to prevent duplicates
   - Launches Telegraf for metrics collection
   - Starts MQTT bridge server
   - Spawns services in separate GNOME Terminal tabs

## Setup & Installation

### Prerequisites

- Python 3.8+
- ROS2 (installed and sourced)
- MQTT broker (running on localhost:1883)
- InfluxDB (running on localhost:8086)
- MongoDB (configured and accessible)
- Telegraf (optional, for metrics collection)
- GNOME Terminal (for auto_server_setup.sh)

### Environment Variables

Required environment variables for authentication:

```bash
# InfluxDB
INFLUX_TOKEN=your_influxdb_token
ORG=CDEI-UPC
BUCKET=ROS2DATA

# MongoDB
# Configure connection details in code
```

### Installation Steps

1. Clone the repository
2. Install Python dependencies:
   ```bash
   pip install fastapi pydantic rclpy paho-mqtt pymongo influxdb-client
   ```
3. Update configuration parameters:
   - InfluxDB URL and credentials in `fast_api_bridge.py`
   - MongoDB connection settings in `mqtt_bridge_server.py`
   - MQTT broker host/port if not localhost:1883
   - ROS2 node IP address (default: 147.83.52.40)

## Running the Server

### Automated Setup (Recommended)

Run the automated setup script:

```bash
sh auto_server_setup.sh
```

This will:
- Kill any existing Telegraf and MQTT server processes
- Start Telegraf in a new terminal tab
- Start the MQTT bridge server in another tab
- Maintain separate terminal sessions for easy monitoring

### Manual Startup

If not using the automated script, set the environment variable before running:

```bash
export LAUNCHED_VIA_SETUP=1
python3 mqtt_bridge_server.py
```

Start the FastAPI server separately:

```bash
python3 -m uvicorn fast_api_bridge:app --reload --host 0.0.0.0 --port 8000
```

## API Endpoints

The FastAPI bridge server provides endpoints for querying sensor data:

- **Query Data**: Retrieve stored sensor readings from InfluxDB
- **List Data**: Fetch data with pagination (default limit: 10)
- Response format: JSON with CSV export capability

## Data Flow

```
Sensors (MQTT) → MQTT Server → MongoDB/InfluxDB ↓
                                                  ↓
                                            FastAPI Server
                                                  ↓
                                            Clients/REST API
```

## Security

- The MQTT bridge server enforces secure execution via `auto_server_setup.sh`
- Direct execution without the setup script will exit with an error
- This prevents accidental data loss from improperly configured instances

## Configuration

Key configuration parameters are located in:

- **mqtt_bridge_server.py**:
  - MQTT broker host and port
  - MongoDB connection details
  
- **fast_api_bridge.py**:
  - InfluxDB URL, token, organization, and bucket
  - Query result limitations

- **auto_server_setup.sh**:
  - Server IP detection
  - Telegraf configuration
  - Service ports

## Monitoring

Monitor running services:

```bash
ps aux | grep python3
ps aux | grep telegraf
```

## Troubleshooting

- **MQTT Connection Failed**: Ensure MQTT broker is running on localhost:1883
- **InfluxDB Connection Failed**: Check InfluxDB is running on localhost:8086 and token is valid
- **ROS2 Errors**: Ensure ROS2 is properly sourced in your environment
- **Direct Execution Error**: Always use `sh auto_server_setup.sh` to start the server

