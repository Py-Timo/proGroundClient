import dash
from dash import dcc, html, Input, Output, State
import paho.mqtt.client as mqtt
import threading
import json
import pandas as pd
import plotly.express as px
import datetime
#
app = dash.Dash(__name__)
server = app.server
# MQTT Configuration
BROKER = "broker.hivemq.com"
#BROKER = "155.190.42.5"
#BROKER = "192.168.11.179"
PORT = 1883 # 8000#
TOPIC = "esp32/devices/#"  # Use wildcard for multiple devices

# Shared Data Dictionary
data = {"device1": {"voltage": 0, "current": 0},
        "device2": {"voltage": 0, "current": 0},
        "device3": {"voltage": 0, "current": 0},
        "device4": {"voltage": 0, "current": 0}}

# Historical data for CSV
history = {"time": [], "device": [], "voltage": [], "current": []}

# Dash App Setup
app = dash.Dash(__name__)
app.layout = html.Div(
    style={"textAlign": "center", "fontFamily": "Arial, sans-serif", "backgroundColor": "#f4f4f9", "padding": "50px"},
    children=[
        html.H1("ESP32 Data Monitor", style={"color": "#333", "marginBottom": "30px"}),
        dcc.Dropdown(
            id="device-dropdown",
            options=[
                {"label": "Device 1", "value": "device1"},
                {"label": "Device 2", "value": "device2"},
                {"label": "Device 3", "value": "device3"},
                {"label": "Device 4", "value": "device4"}
            ],
            value="device1",
            placeholder="Select a device",
            style={
                "width": "50%", "margin": "auto", "padding": "10px", "borderRadius": "5px", "border": "1px solid #ccc",
                "boxShadow": "0px 2px 5px rgba(0,0,0,0.1)"
            }
        ),
        html.Button(
            "Connect",
            id="connect-button",
            n_clicks=0,
            style={
                "marginTop": "20px", "padding": "10px 20px", "fontSize": "16px", "color": "white", "backgroundColor": "#007BFF",
                "border": "none", "borderRadius": "5px", "cursor": "pointer", "boxShadow": "0px 3px 6px rgba(0,0,0,0.1)"
            }
        ),
        html.Div(id="connection-status", style={"marginTop": "20px", "fontSize": "16px", "color": "#007BFF"}),

        # Export Data Button (moved below the Connect button)
        html.Button(
            "Export Data to CSV",
            id="export-button",
            n_clicks=0,
            style={
                "marginTop": "20px", "padding": "10px 20px", "fontSize": "16px", "color": "white", "backgroundColor": "#28a745",
                "border": "none", "borderRadius": "5px", "cursor": "pointer", "boxShadow": "0px 3px 6px rgba(0,0,0,0.1)"
            }
        ),

        # Voltage Graph
        dcc.Graph(id="voltage-graph", style={"marginTop": "30px", "width": "80%", "margin": "auto"}),

        # Current Graph
        dcc.Graph(id="current-graph", style={"marginTop": "30px", "width": "80%", "margin": "auto"}),

        dcc.Interval(id="update-interval", interval=1000, n_intervals=0, disabled=True)  # Initially disabled
    ]
)

# MQTT Client Reference
mqtt_client = mqtt.Client()

# MQTT Callback Functions
def on_connect(client, userdata, flags, rc):
    global connection_status
    if rc == 0:
        print("Connected to MQTT Broker!")
        connection_status = "Connected to MQTT Broker"
        client.subscribe(TOPIC)
    else:
        print(f"Failed to connect, return code {rc}")
        connection_status = f"Connection failed (code {rc})"

def on_message(client, userdata, msg):
    try:
        payload = json.loads(msg.payload.decode())
        device_id = payload.get("device_id", "unknown")
        if device_id in data:
            data[device_id]["voltage"] = payload.get("voltage", 0)
            data[device_id]["current"] = payload.get("current", 0)
            # Add data to history for plotting
            history["time"].append(pd.Timestamp.now())
            history["device"].append(device_id)
            history["voltage"].append(payload.get("voltage", 0)) ; print(history["voltage"][-1])
            history["current"].append(payload.get("current", 0)) ; print(history["current"][-1])
    except Exception as e:
        print(f"Error processing message: {e}")

# Dash Callback to Start MQTT Client
@app.callback(
    [Output("update-interval", "disabled"),
     Output("connection-status", "children")],
    [Input("connect-button", "n_clicks")],
    [State("device-dropdown", "value")]
)
def start_mqtt_process(n_clicks, selected_device):
    global mqtt_client, connection_status

    if n_clicks > 0:
        # Start MQTT Client
        if mqtt_client._thread is None:
            mqtt_client.on_connect = on_connect
            mqtt_client.on_message = on_message

            threading.Thread(target=lambda: mqtt_client.connect(BROKER, PORT, 60) or mqtt_client.loop_forever(), daemon=True).start()

        return False, f"Status: {connection_status}. Listening to {selected_device}."
    else:
        return True, "Press 'Connect' to start."

# Dash Callback to Update Graph
@app.callback(
    [Output("voltage-graph", "figure"),
     Output("current-graph", "figure")],
    [Input("update-interval", "n_intervals"),
     State("device-dropdown", "value")]
)
def update_graph(_, selected_device):
    # Filter historical data for the selected device
    df = pd.DataFrame(history)
    df = df[df["device"] == selected_device]

    # Create Voltage Graph with Red Color
    if df.empty:
        voltage_fig = px.line(title="No Voltage Data Available", template="plotly_white")
    else:
        voltage_fig = px.line(
            df, x="time", y="voltage", 
            labels={"value": "Voltage (V)", "time": "Timestamp"},
            title=f"Voltage for {selected_device}",
            template="plotly_white"
        )
        voltage_fig.update_traces(line=dict(color="red"))  # Set Voltage graph color to Red
        voltage_fig.update_layout(
            xaxis_title="Time",
            yaxis_title="Voltage (V)",
            margin=dict(l=20, r=20, t=50, b=20)
        )

    # Create Current Graph with Green Color
    if df.empty:
        current_fig = px.line(title="No Current Data Available", template="plotly_white")
    else:
        current_fig = px.line(
            df, x="time", y="current", 
            labels={"value": "Current (A)", "time": "Timestamp"},
            title=f"Current for {selected_device}",
            template="plotly_white"
        )
        current_fig.update_traces(line=dict(color="green"))  # Set Current graph color to Green
        current_fig.update_layout(
            xaxis_title="Time",
            yaxis_title="Current (A)",
            margin=dict(l=20, r=20, t=50, b=20)
        )

    return voltage_fig, current_fig

# Dash Callback to Export Data to CSV
@app.callback(
    Output("export-button", "n_clicks"),
    [Input("export-button", "n_clicks")]
)
def export_data_to_csv(n_clicks):
    if n_clicks > 0:
        # Convert history to a DataFrame, separating the date from the time
        df = pd.DataFrame({
            "Date": [timestamp.date() for timestamp in history["time"]],  # Extract the date from the timestamp
            "Time": [timestamp.time() for timestamp in history["time"]],  # Extract the time from the timestamp
            "Device": history["device"],
            "Voltage": history["voltage"],
            "Current": history["current"]
        })
        
        # Save all the data to a single CSV file
        df.to_csv("device_data.csv", index=False)

        print("Data exported to CSV successfully.")
        return 0  # Reset the button click counter after export

    return n_clicks

# Run the App
if __name__ == "__main__":
    app.run(port=8080)
    # app.run_server(debug=True)
