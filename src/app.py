import dash
from dash import dcc, html, Input, Output, State
import paho.mqtt.client as mqtt
import threading
import json
import pandas as pd
import plotly.express as px
import datetime

# MQTT Configuration
BROKER = "broker.hivemq.com"
PORT = 1883
TOPIC = "esp32/devices/#"

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
        html.H1("Pro Ground Client ", style={"color": "#333", "marginBottom": "30px"}),
        html.H1("Data Monitoring ", style={"color": "#333", "marginBottom": "30px"}),
        html.Div(
            style={"display": "flex", "justifyContent": "center", "alignItems": "center"},
            children=[
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
                        "width": "40%", "margin": "auto", "padding": "10px", "borderRadius": "5px", "border": "1px solid #ccc",
                        "boxShadow": "0px 2px 5px rgba(0,0,0,0.1)"
                    }
                ),
                dcc.Input(
                    id="device-input",
                    type="text",
                    placeholder="Or type device name",
                    style={
                        "width": "40%", "marginLeft": "10px", "padding": "10px", "borderRadius": "5px", "border": "1px solid #ccc",
                        "boxShadow": "0px 2px 5px rgba(0,0,0,0.1)"
                    }
                )
            ]
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

        html.Div(
            id="data-display",
            style={"marginTop": "20px", "fontSize": "18px", "color": "#333"}
        ),

        html.Button(
            "Export Data to CSV",
            id="export-button",
            n_clicks=0,
            style={
                "marginTop": "20px", "padding": "10px 20px", "fontSize": "16px", "color": "white", "backgroundColor": "#28a745",
                "border": "none", "borderRadius": "5px", "cursor": "pointer", "boxShadow": "0px 3px 6px rgba(0,0,0,0.1)"
            }
        ),

        dcc.Graph(id="voltage-graph", style={"marginTop": "30px", "width": "80%", "margin": "auto"}),

        dcc.Graph(id="current-graph", style={"marginTop": "30px", "width": "80%", "margin": "auto"}),

        dcc.Interval(id="update-interval", interval=1000, n_intervals=0, disabled=True)
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
            history["time"].append(pd.Timestamp.now())
            history["device"].append(device_id)
            history["voltage"].append(payload.get("voltage", 0))
            history["current"].append(payload.get("current", 0))
    except Exception as e:
        print(f"Error processing message: {e}")

# Dash Callback to Start MQTT Client
@app.callback(
    [Output("update-interval", "disabled"),
     Output("connection-status", "children")],
    [Input("connect-button", "n_clicks")],
    [State("device-dropdown", "value"),
     State("device-input", "value")]
)
def start_mqtt_process(n_clicks, selected_device, typed_device):
    global mqtt_client, connection_status

    device = typed_device if typed_device else selected_device

    if n_clicks > 0:
        if mqtt_client._thread is None:
            mqtt_client.on_connect = on_connect
            mqtt_client.on_message = on_message

            threading.Thread(target=lambda: mqtt_client.connect(BROKER, PORT, 60) or mqtt_client.loop_forever(), daemon=True).start()

        return False, f"Status: {connection_status}. Listening to {device}."
    else:
        return True, "Press 'Connect' to start."

# Dash Callback to Update Data Display
@app.callback(
    Output("data-display", "children"),
    [Input("update-interval", "n_intervals"),
     State("device-dropdown", "value"),
     State("device-input", "value")]
)
def update_data_display(_, selected_device, typed_device):
    device = typed_device if typed_device else selected_device
    voltage = data[device]["voltage"]
    current = data[device]["current"]
    return f"Device: {device} | Voltage: {voltage} V | Current: {current} A"

# Dash Callback to Update Graph
@app.callback(
    [Output("voltage-graph", "figure"),
     Output("current-graph", "figure")],
    [Input("update-interval", "n_intervals"),
     State("device-dropdown", "value"),
     State("device-input", "value")]
)
def update_graph(_, selected_device, typed_device):
    device = typed_device if typed_device else selected_device

    df = pd.DataFrame(history)
    df = df[df["device"] == device]

    if df.empty:
        voltage_fig = px.line(title="No Voltage Data Available", template="plotly_white")
    else:
        voltage_fig = px.line(
            df, x="time", y="voltage",
            labels={"value": "Voltage (V)", "time": "Timestamp"},
            title=f"Voltage for {device}",
            template="plotly_white"
        )
        voltage_fig.update_traces(line=dict(color="red"))
        voltage_fig.update_layout(
            xaxis_title="Time",
            yaxis_title="Voltage (V)",
            margin=dict(l=20, r=20, t=50, b=20)
        )

    if df.empty:
        current_fig = px.line(title="No Current Data Available", template="plotly_white")
    else:
        current_fig = px.line(
            df, x="time", y="current",
            labels={"value": "Current (A)", "time": "Timestamp"},
            title=f"Current for {device}",
            template="plotly_white"
        )
        current_fig.update_traces(line=dict(color="green"))
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
        df = pd.DataFrame({
            "Date": [timestamp.date() for timestamp in history["time"]],
            "Time": [timestamp.time() for timestamp in history["time"]],
            "Device": history["device"],
            "Voltage": history["voltage"],
            "Current": history["current"]
        })
        
        df.to_csv("device_data.csv", index=False)

        print("Data exported to CSV successfully.")
        return 0

    return n_clicks
#######################################
# Expose the server for Gunicorn
server = app.server  
# Run the App
if __name__ == "__main__":
    app.run_server(host="0.0.0.0", port=8080)
