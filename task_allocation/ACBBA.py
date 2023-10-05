import copy
import math
import random
import time
from dataclasses import dataclass
from functools import cache
from typing import List

import numpy as np

from task_allocation.Task import TrajectoryTask


@dataclass
class BidInformation:
    y: float
    z: int
    t: float
    j: int
    k: int
    # winning_score: float
    # winning_agent: int
    # timestamp: float
    # task_id: int
    # sender_id: int


class agent:
    def __init__(
        self,
        state,
        id,
        capacity=0,
        environment=None,
        tasks=None,
        color=None,
        point_estimation=False,
    ):
        self.environment = environment
        self.tasks = None
        if tasks is not None:
            self.tasks = {x.id: x for x in copy.deepcopy(tasks)}

        self.use_single_point_estimation = point_estimation
        if color is None:
            self.color = (
                random.uniform(0, 1),
                random.uniform(0, 1),
                random.uniform(0, 1),
            )
        else:
            self.color = color

        # TODO this should be configurable
        self.max_velocity = 3
        self.max_acceleration = 1

        # Agent ID
        self.id = id

        # Local Winning Agent List
        self.z = {}
        # Local Winning Bid List
        self.y = {}
        # Time Stamp List
        self.t = {}
        # Bundle
        self.bundle = []
        # Path
        self.path = []
        # Maximum task capacity
        if capacity is None:
            raise Exception("Error: agent capacity cannot be None")
        else:
            self.capacity = capacity

        # initialize state
        if state is None:
            raise Exception("ERROR: Initial state cannot be None")
        else:
            self.set_state(state.coords[0])
        # socre function parameters
        self.Lambda = 0.95

        self.removal_list = {}
        self.removal_threshold = 15
        self.message_history = []

    def getPathTasks(self) -> List[TrajectoryTask]:
        result = []
        for task in self.path:
            result.append(self.tasks.get(task))
        return result

    def getTravelPath(self):
        assigned_tasks = self.getPathTasks()
        full_path = []
        if len(assigned_tasks) > 0:
            path, dist = self.environment.find_shortest_path(self.state, assigned_tasks[0].start, free_space_after=False, verify=False)
            full_path.extend(path)
            for i in range(len(assigned_tasks) - 1):
                full_path.extend(assigned_tasks[i].trajectory.coords)
                path, dist = self.environment.find_shortest_path(assigned_tasks[i].end, assigned_tasks[i + 1].start, free_space_after=False, verify=False)
                full_path.extend(path)
            full_path.extend(assigned_tasks[-1].trajectory.coords)
        return full_path

    def getPath(self):
        return self.path

    def getBundle(self):
        return self.bundle

    def set_state(self, state):
        self.state = state

    def send_message(self):
        return self.y, self.z, self.t

    def getTotalTravelCost(self, task_list: List[TrajectoryTask]):
        total_cost = 0
        if len(task_list) != 0:
            # Add the cost of travelling to the first task
            total_cost = self.getTravelCost(self.state, task_list[0].start)
            # The cost of travelling between tasks
            for t_index in range(len(task_list) - 1):
                total_cost += self.getTravelCost(task_list[t_index].end, task_list[t_index + 1].start)
            # The cost of executing the task
            for t_index in range(len(task_list)):
                total_cost += self.distanceToCost(task_list[t_index].length)
            # Add the cost of returning home
            total_cost += self.getTravelCost(self.state, task_list[-1].end)
        return total_cost

    # This is only used for evaluations!
    def getTotalPathLength(self):
        finalTaskList = self.getPathTasks()
        total_dist = 0
        total_task_length = 0
        if len(finalTaskList) != 0:
            # Add the cost of travelling to the first task
            total_dist = np.linalg.norm(np.array(self.state) - np.array(finalTaskList[0].start))
            for t_index in range(len(finalTaskList) - 1):
                total_dist += np.linalg.norm(np.array(finalTaskList[t_index].end) - np.array(finalTaskList[t_index + 1].start))
            for t_index in range(len(finalTaskList)):
                total_task_length += finalTaskList[t_index].length
            # Add the cost of returning home
            total_dist += np.linalg.norm(np.array(self.state) - np.array(finalTaskList[-1].end))
            # Add the total task length
            total_dist += total_task_length
        return total_dist, total_task_length

    
    def distanceToCost(self, dist):
        # Velocity ramp
        d_a = (self.max_velocity**2) / self.max_acceleration
        result = math.sqrt(4 * dist / self.max_acceleration) if dist < d_a else self.max_velocity / self.max_acceleration + dist / self.max_velocity
        return result

    def getDistance(self, start, end):
        # If there is no environment defined, use euclidean
        if self.environment is None:
            # This is a optimised way of calculating euclidean distance: https://stackoverflow.com/questions/37794849/efficient-and-precise-calculation-of-the-euclidean-distance
            dist = [(a - b) ** 2 for a, b in zip(start, end)]
            dist = math.sqrt(sum(dist))
            dist = dist / self.max_velocity
        else:
            path, dist = self.environment.find_shortest_path(start, end, verify=True)

        return dist

    @cache
    def getTravelCost(self, start, end):
        # If there is no environment defined, use euclidean
        return self.distanceToCost(self.getDistance(start,end))

    def getTimeDiscountedReward(self, cost, task: TrajectoryTask):
        return self.Lambda ** (cost) * task.reward

    # S_i calculation of the agent
    def calculatePathReward(self):
        S_p = 0
        if len(self.path) > 0:
            travel_cost = self.getTravelCost(self.state, self.tasks[self.path[0]].start)
            S_p += self.Lambda ** (travel_cost) * self.tasks[self.path[0]].reward
            for p_idx in range(len(self.path) - 1):
                travel_cost += self.getTravelCost(self.tasks[self.path[p_idx]].end, self.tasks[self.path[p_idx + 1]].start)
                S_p += self.getTimeDiscountedReward(travel_cost, self.tasks[self.path[p_idx]])
        return S_p

    def getMinTravelCost(self, point, task: TrajectoryTask):
        distance_to_start = self.getTravelCost(point, task.start)
        distance_to_end = self.getTravelCost(point, task.end)
        result = distance_to_start
        shouldBeReversed = False
        if distance_to_start > distance_to_end:
            result = distance_to_end
            shouldBeReversed = True
        return result, shouldBeReversed

    # Calculate the path reward with task j at index n
    def calculatePathRewardWithNewTask(self, j, n):
        temp_path = list(self.path)
        temp_path.insert(n, j)
        # print(j)
        is_reversed = False
        # travel cost to first task
        travel_cost = self.getTravelCost(self.state, self.tasks[temp_path[0]].start)
        S_p = self.getTimeDiscountedReward(
            travel_cost,
            self.tasks[temp_path[0]],
        )

        # Use a single point instead of greedily optimising the direction
        if self.use_single_point_estimation:
            for p_idx in range(len(temp_path) - 1):
                travel_cost += self.getTravelCost(self.tasks[temp_path[p_idx]].end, self.tasks[temp_path[p_idx + 1]].start)
                S_p += self.getTimeDiscountedReward(travel_cost, self.tasks[temp_path[p_idx]])
        else:
            for p_idx in range(len(temp_path) - 1):
                if p_idx == n :
                    # print(temp_path[p_idx + 1])
                    # The task is inserted at n, when evaluating the task use n-1 to determine whether it should be reversed
                    temp_cost, is_reversed = self.getMinTravelCost(self.tasks[temp_path[p_idx]].end, self.tasks[temp_path[p_idx + 1]])
                    travel_cost += temp_cost
                else:
                    travel_cost += self.getTravelCost(self.tasks[temp_path[p_idx]].end, self.tasks[temp_path[p_idx + 1]].start)
                S_p += self.getTimeDiscountedReward(travel_cost, self.tasks[temp_path[p_idx + 1]])

        # Add the cost for returning home
        travel_cost += self.getTravelCost(self.tasks[temp_path[-1]].end, self.state)
        S_p += self.getTimeDiscountedReward(travel_cost, self.tasks[temp_path[-1]])
        return S_p, is_reversed

    def getCij(self):
        """
        Returns the cost list c_ij for agent i where the position n results in the greatest reward
        """
        # Calculate Sp_i
        S_p = self.calculatePathReward()
        # init
        best_pos = None
        c = 0
        reverse = None
        best_task = None
        # try all tasks
        for j, task in self.tasks.items():
            # If already in the bundle list
            if j in self.bundle or self.removal_list.get(j, 0) > self.removal_threshold:
                continue  # Do not include if already in the bundle or if the removal threshold is exceeded
            else:
                # for each j calculate the path reward at each location in the local path
                for n in range(len(self.path) + 1):
                    S_pj, should_be_reversed = self.calculatePathRewardWithNewTask(j, n)
                    c_ijn = S_pj - S_p
                    
                    if c_ijn > c and c_ijn > self.y.get(j, -1):
                        c = c_ijn  # Store the cost
                        best_pos = n
                        reverse = should_be_reversed
                        best_task = j

        # reverse the task with max reward if necesarry
        if reverse:
            self.tasks[j].reverse()

        return best_task, best_pos, c

    def build_bundle(self):
        if self.tasks is None:
            return
        bid_list = []
        bundle_time = time.monotonic()
        while self.getTotalTravelCost(self.getPathTasks()) <= self.capacity:
            J_i, n_J, c = self.getCij()
            if J_i is None:
                break
            self.bundle.append(J_i)
            self.path.insert(n_J, J_i)

            self.y[J_i] = c
            self.z[J_i] = self.id
            self.t[J_i] = bundle_time  # Update the time of the winning bet
            bid_list.append(BidInformation(y=c, z=self.id, t=bundle_time, j=J_i, k=self.id))
        return bid_list

    def __update_time(self, task):
        self.t[task] = time.monotonic()

    def __action_rule(self, k, j, task, z_kj, y_kj, t_kj, z_ij, y_ij, t_ij) -> BidInformation:
        eps = 5
        i = self.id
        sender_info = BidInformation(y=y_kj, z=z_kj, t=t_kj, j=j, k=self.id)
        own_info = BidInformation(y_ij, z_ij, t_ij, j, self.id)
        if z_kj == k:  # Rule 1 Agent k thinks k is z_kj
            if z_ij == i:  # Rule 1.1
                if y_kj > y_ij:
                    self.__update(y_kj, z_kj, t_kj, task)
                    return sender_info
                elif y_kj == y_ij and z_kj < z_ij:
                    self.__update(y_kj, z_kj, t_kj, task)
                    return sender_info
                elif y_kj < y_ij:
                    self.__update_time(task)
                    return own_info

            elif z_ij == k:  # Rule 1.2
                if t_kj > t_ij:
                    self.__update(y_kj, z_kj, t_kj, task)
                    return None
                elif abs(t_kj - t_ij) < eps:
                    self.__leave()
                    return None
                elif t_kj < t_ij:
                    self.__leave()
                    return None

            elif z_ij != i and z_ij != k:  # Rule 1.3
                if y_kj > y_ij and t_kj >= t_ij:
                    self.__update(y_kj, z_kj, t_kj, task)
                    return sender_info

                elif y_kj < y_ij and t_kj <= t_ij:
                    self.__leave()
                    return own_info

                elif y_kj == y_ij:
                    self.__leave()
                    return own_info

                elif y_kj < y_ij and t_kj > t_ij:
                    self.__reset(task)
                    return sender_info

                elif y_kj > y_ij and t_kj < t_ij:
                    self.__reset(task)
                    return sender_info

            elif z_ij == -1:  # Rule 1.4
                self.__update(y_kj, z_kj, t_kj, task)
                return sender_info

        elif z_kj == i:  # Rule 2 Agent k thinks winning agent is i
            if z_ij == i and (abs(t_kj - t_ij) < eps):  # Rule 2.1 # Agent i thinks itself is the winner
                self.__leave()
                return None

            elif z_ij == k:
                self.__reset(task)
                return sender_info

            elif z_ij != i and z_ij != k:
                self.__leave()
                return own_info

            elif z_ij == -1:
                self.__leave()
                return own_info

        elif z_kj != k and z_kj != i:  # Rule 3 Agent k think the winner of task j is not the itself nor agent i
            if z_ij == i:  # Rule 3.1
                if y_kj > y_ij:
                    self.__update(y_kj, z_kj, t_kj, task)
                    return sender_info

                elif y_kj == y_ij and z_kj < z_ij:
                    self.__update(y_kj, z_kj, t_kj, task)
                    return sender_info

                elif y_kj < y_ij:
                    self.__update_time(task)
                    return own_info

            elif z_ij == k:  # Rule 3.2
                if t_kj >= t_ij:
                    self.__update(y_kj, z_kj, t_kj, task)
                    return sender_info
                elif t_kj < t_ij:
                    self.__reset(task)
                    return sender_info

            elif z_kj == z_ij:  # Rule 3.3
                if t_kj > t_ij:
                    self.__update(y_kj, z_kj, t_kj, task)
                    return None
                elif abs(t_kj - t_ij) <= eps:
                    self.__leave()
                    return None
                elif t_kj < t_ij:
                    self.__leave()
                    return None

            elif z_ij != i and z_ij != k:  # Rule 3.4
                if y_kj > y_ij and t_kj >= t_ij:
                    self.__update(y_kj, z_kj, t_kj, task)
                    return sender_info
                elif y_kj < y_ij and t_kj <= t_ij:
                    self.__leave()
                    return own_info
                elif y_kj == y_ij:
                    self.__leave()
                    return own_info
                elif y_kj < y_ij and t_kj > t_ij:
                    self.__reset(task)
                    return sender_info
                elif y_kj > y_ij and t_kj < t_ij:
                    self.__reset(task)
                    return sender_info

            elif z_ij == -1:  # Rule 3.5
                self.__update(y_kj, z_kj, t_kj, task)
                return sender_info

        elif z_kj == -1:  # Rule 4 Agent k thinks None is z_kj
            if z_ij == i:
                self.__leave()
                return own_info
            elif z_ij == k:
                self.__update(y_kj, z_kj, t_kj, task)
                return sender_info
            elif z_ij != i and z_ij != k:
                if t_kj > t_ij:
                    self.__update(y_kj, z_kj, t_kj, task)
                    return sender_info
            elif z_ij == -1:
                self.__leave()
                return None
        # Default leave and rebroadcast own info
        self.__leave()
        return own_info

    def __rebroadcast(self, information):
        y = information["y"]
        z = information["z"]
        t = information["t"]
        self.send_information(y, z, t, self.id)

    def __receive_information(self):
        raise NotImplementedError()
        # message = self.my_socket.recieve(self.agent)
        # if message is None:
        #     return None
        # return message

    def send_information(self, y, z, t, k):
        """This function is used for sharing information between agents and is not implemented in this base class
        Raises
        ------
        NotImplementedError
            _description_
        """
        raise NotImplementedError()
        # msg = {self.agent: {"y": y, "z": z, "t": t}}
        # self.my_socket.send(self.agent, msg, k)

    def update_task_async(self, bids: List[BidInformation]):
        # Update Process
        rebroadcasts = []
        for bid_info in bids:
            j = bid_info.j
            k = bid_info.k

            # Own info
            y_ij = self.y.get(j, 0)
            z_ij = self.z.get(j, -1)
            t_ij = self.t.get(j, 0)

            # Recieve info
            y_kj = bid_info.y  # Winning bids
            z_kj = bid_info.z  # Winning agent
            t_kj = bid_info.t  # Timestamps

            rebroadcast = self.__action_rule(k=k, j=j, task=j, z_kj=z_kj, y_kj=y_kj, t_kj=t_kj, z_ij=z_ij, y_ij=y_ij, t_ij=t_ij)
            if rebroadcast:
                rebroadcasts.append(rebroadcast)
        return rebroadcasts

    def update_task(self, Y: List[BidInformation]):
        # Update Process
        rebroadcasts = []

        for k in Y:
            for j in self.tasks:
                # Recieve info
                y_kj = Y[k][0].get(j, 0)  # Winning bids
                z_kj = Y[k][1].get(j, -1)  # Winning agent
                t_kj = Y[k][2].get(j, 0)  # Timestamps

                # Own info
                y_ij = self.y.get(j, 0)
                z_ij = self.z.get(j, -1)
                t_ij = self.t.get(j, 0)
                # TODO parse the information in a better way
                rebroadcast = self.__action_rule(k=k, j=j, task=j, z_kj=z_kj, y_kj=y_kj, t_kj=t_kj, z_ij=z_ij, y_ij=y_ij, t_ij=t_ij)
                if rebroadcast:
                    # TODO save the rebroadcasts
                    rebroadcasts.append(rebroadcast)
        return rebroadcasts

    def __update(self, y_kj, z_kj, t_kj, j):
        """
        Update values
        """
        self.y[j] = y_kj
        self.z[j] = z_kj
        self.t[j] = t_kj
        self.__update_path(j)

    def __update_path(self, task):
        if task not in self.bundle:
            return
        index = self.bundle.index(task)
        b_retry = self.bundle[index + 1 :]
        for idx in b_retry:
            self.y[idx] = 0
            self.z[idx] = -1
            self.t[idx] = time.monotonic()

        self.removal_list[task] = self.removal_list.get(task, 0) + 1
        self.path = [num for num in self.path if num not in self.bundle[index:]]
        self.bundle = self.bundle[:index]

    def __reset(self, task):
        self.y[task] = 0
        self.z[task] = -1
        self.t[task] = time.monotonic()
        self.__update_path(task)

    def __leave(self):
        """
        Do nothing
        """
        return
