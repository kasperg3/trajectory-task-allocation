import copy
import math
import random

import numpy as np

from task_allocation import Task


class agent:
    def __init__(
        self,
        id=None,
        agent_num=None,
        L_t=None,
        state=None,
        tasks=None,
        color=None,
        point_estimation=False,
    ):
        self.tasks = copy.deepcopy(tasks)
        self.task_num = len(tasks)
        self.task_idx = list(range(self.task_num))
        self.use_single_point_estimation = point_estimation
        self.agent_num = agent_num
        if color is None:
            self.color = (
                random.uniform(0, 1),
                random.uniform(0, 1),
                random.uniform(0, 1),
            )
        else:
            self.color = color
        self.max_velocity = 3
        self.max_acceleration = 1

        # Agent ID
        self.id = id

        # Local Winning Agent List
        self.winning_agents = np.ones(self.task_num, dtype=np.int8) * self.id
        # Local Winning Bid List
        self.winning_bids = np.array([0 for _ in range(self.task_num)], dtype=np.float64)
        # Bundle
        self.bundle = []
        # Path
        self.path = []
        # Maximum task capacity
        if L_t is None:
            self.L_t = 999999
        else:
            self.L_t = L_t

        # Local Clock
        self.time_step = 0
        # Time Stamp List
        self.timestamps = {a: self.time_step for a in range(self.agent_num)}

        # initialize state
        if state is None:
            self.set_state(
                np.random.uniform(low=0, high=1, size=(1, 2)).squeeze()
            )  # Agent State (Position)
        else:
            self.set_state(state.squeeze())
        # socre function parameters
        self.Lambda = 0.95

        self.removal_list = np.zeros(self.task_num, dtype=np.int8)
        self.removal_threshold = 15

    def getPathTasks(self):
        return self.tasks[self.path]

    def getPath(self):
        return self.path

    def getBundle(self):
        return self.bundle

    def tau(self, j):
        pass

    def set_state(self, state):
        self.state = state

    def send_message(self):
        return self.winning_bids.tolist(), self.winning_agents.tolist(), self.timestamps

    def receive_message(self, Y):
        self.Y = Y

    def getTotalTravelCost(self, task_list):
        total_cost = 0
        if len(task_list) != 0:
            # Add the cost of travelling to the first task
            total_cost = self.getTravelCost(self.state.squeeze(), task_list[0].start)
            for t_index in range(len(task_list) - 1):
                total_cost += self.getTravelCost(task_list[t_index].end, task_list[t_index + 1].start)
            for t_index in range(len(task_list)):
                total_cost += self.getTravelCost(task_list[t_index].start, task_list[t_index].end)
            # Add the cost of returning home
            total_cost += self.getTravelCost(self.state.squeeze(),task_list[-1].end)
        return total_cost

    # This is only used for evaluations!
    def getTotalPathCost(self):
        finalTaskList = self.getPathTasks()
        total_dist = 0
        total_task_length = 0
        if len(finalTaskList) != 0:
            # Add the cost of travelling to the first task
            total_dist = np.linalg.norm(self.state.squeeze() - finalTaskList[0].start)
            for t_index in range(len(finalTaskList) - 1):
                total_dist += np.linalg.norm(finalTaskList[t_index].end - finalTaskList[t_index + 1].start)
            for t_index in range(len(finalTaskList)):
                total_task_length += np.linalg.norm(finalTaskList[t_index].start - finalTaskList[t_index].end)
            # Add the cost of returning home
            total_dist += np.linalg.norm(self.state.squeeze() - finalTaskList[-1].end)
            # Add the total task length
            total_dist += total_task_length
        return total_dist, total_task_length

    def getTravelCost(self, start, end):
        # Travelcost in seconds
        # This is a optimised way of calculating euclidean distance: https://stackoverflow.com/questions/37794849/efficient-and-precise-calculation-of-the-euclidean-distance
        dist = [(a - b) ** 2 for a, b in zip(start, end)]
        dist = math.sqrt(sum(dist))
        result = dist / self.max_velocity
        # Velocity ramp
        d_a = (self.max_velocity**2) / self.max_acceleration

        result = math.sqrt(4 * dist / self.max_acceleration) if dist < d_a else self.max_velocity / self.max_acceleration + dist / self.max_velocity

        return result  # the cost of travelling in seconds!
        # return np.linalg.norm(start - end) / self.velocity # Old and less efficient

    def getTimeDiscountedReward(self, cost, task):
        return self.Lambda ** (cost) * task.reward

    # S_i calculation of the agent
    def calculatePathReward(self):
        S_p = 0
        if len(self.path) > 0:
            travel_cost = self.getTravelCost(self.state.squeeze(), self.tasks[self.path[0]].start)
            S_p += self.Lambda ** (travel_cost) * self.tasks[self.path[0]].reward
            for p_idx in range(len(self.path) - 1):
                travel_cost += self.getTravelCost(self.tasks[self.path[p_idx]].end, self.tasks[self.path[p_idx + 1]].start)
                S_p += self.getTimeDiscountedReward(travel_cost, self.tasks[self.path[p_idx]])
        return S_p

    def getMinTravelCost(self, point, task: Task.Task):
        distArray = [
            self.getTravelCost(point, task.start),
            self.getTravelCost(point, task.end),
        ]
        minIndex = np.argmin(distArray)
        shouldBeReversed = False
        if distArray[0] > distArray[1]:
            shouldBeReversed = True
        return distArray[minIndex], shouldBeReversed

    # Calculate the path reward with task j at index n
    def calculatePathRewardWithNewTask(self, j, n):
        temp_path = list(self.path)
        temp_path.insert(n, j)
        is_reversed = False
        # travel cost to first task
        travel_cost = self.getTravelCost(
            self.state.squeeze(), self.tasks[temp_path[0]].start)
        S_p = self.getTimeDiscountedReward(
            travel_cost,
            self.tasks[temp_path[0]],
        )

        # Use a single point instead of greedily optimising the direction
        if self.use_single_point_estimation:
            for p_idx in range(len(temp_path) - 1):
                travel_cost += self.getTravelCost(
                    self.tasks[temp_path[p_idx]].end, self.tasks[temp_path[p_idx + 1]].start
                )
                S_p += self.getTimeDiscountedReward(travel_cost, self.tasks[temp_path[p_idx]])
        else:
            for p_idx in range(len(temp_path) - 1):
                if p_idx == n - 1:
                    # The task is inserted at n, when evaluating the task use n-1 to determine whether it should be reversed
                    temp_cost, is_reversed = self.getMinTravelCost(
                        self.tasks[temp_path[p_idx]].end,
                        self.tasks[temp_path[p_idx + 1]],
                    )
                    travel_cost += temp_cost
                else:
                    travel_cost += self.getTravelCost(
                        self.tasks[temp_path[p_idx]].end,
                        self.tasks[temp_path[p_idx + 1]].start,
                    )
                S_p += self.getTimeDiscountedReward(travel_cost, self.tasks[temp_path[p_idx]])

        # Add the cost for returning home
        travel_cost += self.getTravelCost(self.state.squeeze(), self.tasks[temp_path[-1]].end)
        S_p += self.getTimeDiscountedReward(
            travel_cost,
            self.tasks[-1],
        )
        # TODO add an option to return to return to start point
        return S_p, is_reversed

    def getCij(self):
        """
        Returns the cost list c_ij for agent i where the position n results in the greatest reward
        """
        # Calculate Sp_i
        S_p = self.calculatePathReward()
        # init
        best_pos = np.zeros(self.task_num, dtype=int)
        c = np.zeros(self.task_num)
        reverse = np.zeros(self.task_num)
        # try all tasks
        for j in range(self.task_num):
            # If already in bundle list
            if j in self.bundle or self.removal_list[j] > self.removal_threshold:
                c[j] = 0  # Minimum Score
            else:
                # for each j calculate the path reward at each location in the local path
                for n in range(len(self.path) + 1):
                    S_pj, should_be_reversed = self.calculatePathRewardWithNewTask(j, n)
                    c_ijn = S_pj - S_p
                    if c[j] <= c_ijn:
                        c[j] = c_ijn  # Store the cost
                        best_pos[j] = n
                        reverse[j] = should_be_reversed

        return (best_pos, c, reverse)

    def build_bundle(self):
        while self.getTotalTravelCost(self.getPathTasks()) <= self.L_t:
            best_pos, c, reverse = self.getCij()
            h = c > self.winning_bids

            if sum(h) == 0:  # No valid task
                break

            c[~h] = 0
            J_i = np.argmax(c)
            n_J = best_pos[J_i]

            # reverse the task with max reward if necesarry
            if reverse[J_i]:
                self.tasks[J_i].reverse()

            self.bundle.append(J_i)
            self.path.insert(n_J, J_i)

            self.winning_bids[J_i] = c[J_i]
            self.winning_agents[J_i] = self.id

    def update_task(self):
        id_list = list(self.Y.keys())
        id_list.insert(0, self.id)

        # Update time list
        for id in list(self.timestamps.keys()):
            if id in id_list:
                self.timestamps[id] = self.time_step
            else:
                s_list = []
                for neighbor_id in id_list[1:]:
                    s_list.append(self.Y[neighbor_id][2][id])
                if len(s_list) > 0:
                    self.timestamps[id] = max(s_list)

        # Update Process
        for j in range(self.task_num):

            for k in id_list[1:]:
                y_k = self.Y[k][0]
                z_k = self.Y[k][1]
                s_k = self.Y[k][2]
                i = self.id

                z_ij = self.winning_agents[j]
                z_kj = z_k[j]
                y_kj = y_k[j]
                y_ij = self.winning_bids[j]
                # Rule Based Update
                # Rule 1~4
                if z_kj == k:
                    # Rule 1
                    if z_ij == self.id:
                        if y_kj > y_ij:
                            self.__update(j, y_kj, z_kj)
                        elif abs(y_kj - y_ij) < np.finfo(float).eps:  # Tie Breaker
                            if k < self.id:
                                self.__update(j, y_kj, z_kj)
                        else:
                            self.__leave()
                    # Rule 2
                    elif z_ij == k:
                        self.__update(j, y_kj, z_kj)
                    # Rule 3
                    elif z_ij != -1:
                        m = z_ij
                        if (s_k[m] > self.timestamps[m]) or (y_kj > y_ij):
                            self.__update(j, y_kj, z_kj)
                        elif abs(y_kj - y_ij) < np.finfo(float).eps and k < self.id:  # Tie Breaker
                            self.__update(j, y_kj, z_kj)
                    # Rule 4
                    elif z_ij == -1:
                        self.__update(j, y_kj, z_kj)
                    else:
                        raise Exception("Error while updating")
                # Rule 5~8
                elif z_kj == i:
                    # Rule 5
                    if z_ij == i:
                        self.__leave()
                    # Rule 6
                    elif z_ij == k:
                        self.__reset(j)
                    # Rule 7
                    elif z_ij != -1:
                        m = z_ij
                        if s_k[m] > self.timestamps[m]:
                            self.__reset(j)
                    # Rule 8
                    elif z_ij == -1:
                        self.__leave()
                    else:
                        raise Exception("Error while updating")
                # Rule 9~13
                elif z_kj != -1:
                    m = z_kj
                    # Rule 9
                    if z_ij == i:
                        if (s_k[m] >= self.timestamps[m]) and (y_kj > y_ij):
                            self.__update(j, y_kj, z_kj)
                        # Tie Breaker
                        elif (s_k[m] >= self.timestamps[m]) and (abs(y_kj - y_ij) < np.finfo(float).eps and m < self.id):
                            self.__update(j, y_kj, z_kj)
                    # Rule 10
                    elif z_ij == k:
                        if s_k[m] > self.timestamps[m]:
                            self.__update(j, y_kj, z_kj)
                        else:
                            self.__reset(j)
                    # Rule 11
                    elif z_ij == m:
                        if s_k[m] > self.timestamps[m]:
                            self.__update(j, y_kj, z_kj)
                    # Rule 12
                    elif z_ij != -1:
                        n = z_ij
                        if (s_k[m] > self.timestamps[m]) and (s_k[n] > self.timestamps[n]):
                            self.__update(j, y_kj, z_kj)
                        elif (s_k[m] > self.timestamps[m]) and (y_kj > y_ij):
                            self.__update(j, y_kj, z_kj)
                        # Tie Breaker
                        elif (s_k[m] > self.timestamps[m]) and (abs(y_kj - y_ij) < np.finfo(float).eps):
                            if m < n:
                                self.__update(j, y_kj, z_kj)
                        elif (s_k[n] > self.timestamps[n]) and (self.timestamps[m] > s_k[m]):
                            self.__update(j, y_kj, z_kj)
                    # Rule 13
                    elif z_ij == -1:
                        if s_k[m] > self.timestamps[m]:
                            self.__update(j, y_kj, z_kj)
                    else:
                        raise Exception("Error while updating")
                # Rule 14~17
                elif z_kj == -1:
                    # Rule 14
                    if z_ij == i:
                        self.__leave()
                    # Rule 15
                    elif z_ij == k:
                        self.__update(j, y_kj, z_kj)
                    # Rule 16
                    elif z_ij != -1:
                        m = z_ij
                        if s_k[m] > self.timestamps[m]:
                            self.__update(j, y_kj, z_kj)
                    # Rule 17
                    elif z_ij == -1:
                        self.__leave()
                    else:
                        raise Exception("Error while updating")
                else:
                    raise Exception("Error while updating")

        n_bar = len(self.bundle)
        # Get n_bar
        for n in range(len(self.bundle)):
            b_n = self.bundle[n]
            if self.winning_agents[b_n] != self.id and n_bar > n:
                n_bar = n  # Find the minimum n in the agents bundle

        b_idx1 = copy.deepcopy(self.bundle[n_bar + 1:])

        if len(b_idx1) > 0:
            self.winning_bids[b_idx1] = 0
            self.winning_agents[b_idx1] = -1

        tasks_to_delete = self.bundle[n_bar:]

        # Keep track of how many times this particular task has been removed
        if len(tasks_to_delete) != 0:
            self.removal_list[self.bundle[n_bar]] = self.removal_list[self.bundle[n_bar]] + 1

        del self.bundle[n_bar:]

        self.path = [ele for ele in self.path if ele not in tasks_to_delete]

        self.time_step += 1

        converged = False
        # The agent has converged to a solution of no conflicts has been detected
        if len(tasks_to_delete) == 0:
            converged = True

        return converged

    def __update(self, j, y_kj, z_kj):
        """
        Update values
        """
        self.winning_bids[j] = y_kj
        self.winning_agents[j] = z_kj

    def __reset(self, j):
        """
        Reset values
        """
        self.winning_bids[j] = 0
        self.winning_agents[j] = -1  # -1 means "none"

    def __leave(self):
        """
        Do nothing
        """
        pass


class consensus_algorithm:
    def __init__(self) -> None:
        pass

    def solve():
        pass
