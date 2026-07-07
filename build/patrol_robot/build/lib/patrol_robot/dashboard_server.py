import rclpy
from rclpy.node import Node
from nav_msgs.msg import Odometry
from geometry_msgs.msg import Twist
from action_msgs.msg import GoalStatusArray
import threading
import json
import math
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse
import uvicorn

app = FastAPI()
ros_node = None

robot_state = {
    "x": 0.0,
    "y": 0.0,
    "yaw": 0.0,
    "linear_vel": 0.0,
    "angular_vel": 0.0,
    "status": "대기 중",
    "waypoint": 0,
    "total_waypoints": 4
}

connected_clients = []

class DashboardNode(Node):
    def __init__(self):
        super().__init__('dashboard_node')
        self.odom_sub = self.create_subscription(
            Odometry, '/odom', self.odom_callback, 10)
        self.vel_sub = self.create_subscription(
            Twist, '/cmd_vel', self.vel_callback, 10)
        self.get_logger().info('📊 대시보드 노드 시작!')

    def odom_callback(self, msg):
        robot_state["x"] = round(msg.pose.pose.position.x, 3)
        robot_state["y"] = round(msg.pose.pose.position.y, 3)
        q = msg.pose.pose.orientation
        yaw = math.atan2(2*(q.w*q.z + q.x*q.y), 1 - 2*(q.y*q.y + q.z*q.z))
        robot_state["yaw"] = round(math.degrees(yaw), 1)

    def vel_callback(self, msg):
        robot_state["linear_vel"] = round(msg.linear.x, 3)
        robot_state["angular_vel"] = round(msg.angular.z, 3)
        if abs(msg.linear.x) > 0.01:
            robot_state["status"] = "이동 중 🚗"
        elif abs(msg.angular.z) > 0.01:
            robot_state["status"] = "회전 중 🔄"
        else:
            robot_state["status"] = "정지 ⏸"

HTML = """
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <title>🤖 순찰 로봇 대시보드</title>
  <style>
    * { box-sizing: border-box; margin: 0; padding: 0; }
    body { background: #0f1117; color: #e0e0e0; font-family: 'Segoe UI', sans-serif; padding: 24px; }
    h1 { font-size: 22px; margin-bottom: 20px; color: #7eb8f7; }
    .grid { display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; margin-bottom: 20px; }
    .card { background: #1c1f2e; border-radius: 12px; padding: 18px; border: 1px solid #2e3250; }
    .card-label { font-size: 11px; color: #6b7280; text-transform: uppercase; letter-spacing: 0.05em; margin-bottom: 6px; }
    .card-value { font-size: 28px; font-weight: 600; color: #7eb8f7; }
    .card-unit { font-size: 13px; color: #6b7280; margin-left: 4px; }
    .status-box { background: #1c1f2e; border-radius: 12px; padding: 18px; border: 1px solid #2e3250; margin-bottom: 20px; }
    .status-label { font-size: 13px; color: #6b7280; margin-bottom: 8px; }
    .status-value { font-size: 20px; font-weight: 600; color: #34d399; }
    .log-box { background: #1c1f2e; border-radius: 12px; padding: 18px; border: 1px solid #2e3250; height: 200px; overflow-y: auto; }
    .log-title { font-size: 12px; color: #6b7280; margin-bottom: 10px; }
    .log-item { font-size: 12px; color: #9ca3af; padding: 3px 0; border-bottom: 1px solid #2e3250; }
    .log-item span { color: #7eb8f7; margin-right: 8px; }
    .dot { width: 10px; height: 10px; border-radius: 50%; background: #34d399; display: inline-block; margin-right: 8px; animation: pulse 1.5s infinite; }
    @keyframes pulse { 0%,100%{opacity:1} 50%{opacity:0.3} }
  </style>
</head>
<body>
  <h1>🤖 자율 순찰 로봇 대시보드</h1>
  <div class="status-box">
    <div class="status-label"><span class="dot"></span>실시간 상태</div>
    <div class="status-value" id="status">연결 중...</div>
  </div>
  <div class="grid">
    <div class="card">
      <div class="card-label">위치 X</div>
      <div class="card-value" id="pos-x">-<span class="card-unit">m</span></div>
    </div>
    <div class="card">
      <div class="card-label">위치 Y</div>
      <div class="card-value" id="pos-y">-<span class="card-unit">m</span></div>
    </div>
    <div class="card">
      <div class="card-label">방향각</div>
      <div class="card-value" id="yaw">-<span class="card-unit">°</span></div>
    </div>
    <div class="card">
      <div class="card-label">선속도</div>
      <div class="card-value" id="lin-vel">-<span class="card-unit">m/s</span></div>
    </div>
    <div class="card">
      <div class="card-label">각속도</div>
      <div class="card-value" id="ang-vel">-<span class="card-unit">rad/s</span></div>
    </div>
    <div class="card">
      <div class="card-label">순찰 포인트</div>
      <div class="card-value" id="waypoint">-<span class="card-unit">/ 4</span></div>
    </div>
  </div>
  <div class="log-box">
    <div class="log-title">📋 실시간 로그</div>
    <div id="log-list"></div>
  </div>

<script>
  const ws = new WebSocket(`ws://${location.host}/ws`);
  const logList = document.getElementById('log-list');
  let lastStatus = '';

  ws.onmessage = (event) => {
    const d = JSON.parse(event.data);
    document.getElementById('status').textContent = d.status;
    document.getElementById('pos-x').innerHTML = d.x + '<span class="card-unit">m</span>';
    document.getElementById('pos-y').innerHTML = d.y + '<span class="card-unit">m</span>';
    document.getElementById('yaw').innerHTML = d.yaw + '<span class="card-unit">°</span>';
    document.getElementById('lin-vel').innerHTML = d.linear_vel + '<span class="card-unit">m/s</span>';
    document.getElementById('ang-vel').innerHTML = d.angular_vel + '<span class="card-unit">rad/s</span>';
    document.getElementById('waypoint').innerHTML = d.waypoint + '<span class="card-unit">/ 4</span>';

    if (d.status !== lastStatus) {
      const now = new Date().toLocaleTimeString();
      const item = document.createElement('div');
      item.className = 'log-item';
      item.innerHTML = `<span>${now}</span>${d.status}`;
      logList.prepend(item);
      lastStatus = d.status;
    }
  };
</script>
</body>
</html>
"""

@app.get("/")
async def get():
    return HTMLResponse(HTML)

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await websocket.accept()
    connected_clients.append(websocket)
    try:
        while True:
            await websocket.send_text(json.dumps(robot_state))
            await asyncio.sleep(0.1)
    except WebSocketDisconnect:
        connected_clients.remove(websocket)

import asyncio

def ros_spin():
    global ros_node
    rclpy.init()
    ros_node = DashboardNode()
    rclpy.spin(ros_node)

def main():
    ros_thread = threading.Thread(target=ros_spin, daemon=True)
    ros_thread.start()
    uvicorn.run(app, host="0.0.0.0", port=8000)

if __name__ == '__main__':
    main()