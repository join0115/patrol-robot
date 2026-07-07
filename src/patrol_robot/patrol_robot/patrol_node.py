import rclpy
from rclpy.node import Node
from rclpy.action import ActionClient
from nav2_msgs.action import NavigateToPose
from geometry_msgs.msg import PoseStamped
from nav_msgs.msg import Odometry
import math

# 순찰 포인트 정의 (x, y, 방향각도)
WAYPOINTS = [
    ( 0.5,  0.5, 0.0),
    ( 0.5, -0.5, 0.0),
    (-0.5, -0.5, 0.0),
    (-0.5,  0.5, 0.0),
]

class PatrolNode(Node):
    def __init__(self):
        super().__init__('patrol_node')
        self._action_client = ActionClient(self, NavigateToPose, 'navigate_to_pose')
        self.waypoint_index = 0
        self.patrolling = True
        self.get_logger().info('🤖 순찰 로봇 시작!')

    def send_goal(self, x, y, yaw=0.0):
        goal_msg = NavigateToPose.Goal()
        pose = PoseStamped()
        pose.header.frame_id = 'map'
        pose.header.stamp = self.get_clock().now().to_msg()
        pose.pose.position.x = x
        pose.pose.position.y = y
        pose.pose.orientation.z = math.sin(yaw / 2)
        pose.pose.orientation.w = math.cos(yaw / 2)
        goal_msg.pose = pose

        self.get_logger().info(f'📍 목적지 설정: ({x}, {y})')
        self._action_client.wait_for_server()
        send_goal_future = self._action_client.send_goal_async(goal_msg)
        send_goal_future.add_done_callback(self.goal_response_callback)

    def goal_response_callback(self, future):
        goal_handle = future.result()
        if not goal_handle.accepted:
            self.get_logger().warn('❌ 목표 거부됨')
            return
        self.get_logger().info('✅ 목표 수락됨 — 이동 중...')
        result_future = goal_handle.get_result_async()
        result_future.add_done_callback(self.result_callback)

    def result_callback(self, future):
        x, y, _ = WAYPOINTS[self.waypoint_index]
        self.get_logger().info(f'🏁 도착: ({x}, {y})')
        # 다음 waypoint로
        self.waypoint_index = (self.waypoint_index + 1) % len(WAYPOINTS)
        next_wp = WAYPOINTS[self.waypoint_index]
        self.get_logger().info(f'➡ 다음 순찰 포인트: {self.waypoint_index + 1}/{len(WAYPOINTS)}')
        self.send_goal(*next_wp)

def main(args=None):
    rclpy.init(args=args)
    node = PatrolNode()
    # 첫 번째 waypoint로 출발
    node.send_goal(*WAYPOINTS[0])
    rclpy.spin(node)
    rclpy.shutdown()

if __name__ == '__main__':
    main()