#!/usr/bin/env python

import rospy
from geometry_msgs.msg import Pose,PoseStamped
import Tkinter as tk
from std_msgs.msg import String 
import tkMessageBox
import xml.etree.ElementTree as ET
import json
class iliad_goal_manager(object):

	def __init__(self):
		#parameters
		self.orders_file = rospy.get_param('~orders_file',"../config/orkla_orders.xml")
		self.orders_times_file = rospy.get_param('~orders_times_file',"../config/orkla_orders_times.txt")
		self.items_locations_file = rospy.get_param('~items_locations_file',"../config/orkla_item_locations.json")
		self.locations_coordinates_file = rospy.get_param('~locations_coordinates_file',"../config/orkla_location_coordinates.json")

		# ini variables
		self.available_list_updated = 0
		self.missions_started = 0
		self.available_robots = {}
		self.active_robots = {}
		self.next_mission = 0
		self.queued_missions = []
		self.all_missions_added = 0
		self.completed_missions = []
		self.mission_status = {"completed":[],"queued":[],"seconds_left_next":0}
		
		# subscribe to topics
		rospy.Subscriber("/exploration_goal", PoseStamped, self.exploration_goal_callback,queue_size=1)
		rospy.Subscriber("/fleet_status", String, self.fleet_status_callback,queue_size=1)

		# create topic publishers
		self.active_robots_status_pub = rospy.Publisher('/active_robot_status', String,queue_size=10)
		self.mission_status_pub = rospy.Publisher('/mission_status', String,queue_size=10)
		self.coordinator_goal_pub = rospy.Publisher('/coordinator_goal', String,queue_size=10)

		# create timers
		self.assign_missions_and_goals_timer = rospy.Timer(rospy.Duration(0.5),self.assign_missions_and_goals)
		
		#parse input files
		# read orders file
		self.missions = self.parse_orders_file()
		print "\n",self.missions
		# Exmple of missions variable structure with 4 simple orders
		# self.missions = [["pick:soup","go:home"], ["pick:soup","go:home"],["pick:soup","go:home"],["pick:soup","go:home"]]

		self.parse_orders_times_file()
		self.parse_item_locations_file()
		self.parse_location_coordinates_file()


		#self.parse_locations_file()
		self.locations = {"empty_pallet":[1,1,0],"Hallonsoppa":[2,2,0],"Jacky":[3,3,0],"Chocolate":[4,4,0]}

		#start gui variables		
		self.start_gui()
		
		# ini the main loop
		self.run()

	def parse_orders_file(self):
		# the input is an xml file with all the orders to be completed in a day
		missions = []
		mission= []		
		orders = ET.parse(self.orders_file).getroot()
		print "Num of orders: "+str(len(orders))

		for o in range(0,len(orders)):
			print ""
			print "> Order "+str(o)
			for pallet_type in range(0,len(orders[o])):
				if orders[o][pallet_type].tag == "FullPallets":
					print "--> Num of full pallets: " + str(len(orders[o][pallet_type]))
					for pallet in range(0,len(orders[o][pallet_type])):
						print "----> Pallet "+str(pallet)
						item_name = orders[o][pallet_type][pallet][0][0].attrib["name"]
						print "------> Item: "+item_name
						mission.append("go:fullpallet_"+item_name)
						mission.append("pick:fullpallet_"+item_name)

				if orders[o][pallet_type].tag == "MixedPallets":
					print "--> Num of mixed pallets: " + str(len(orders[o][pallet_type]))
					for pallet in range(0,len(orders[o][pallet_type])):
						print "----> Pallet "+str(pallet)
						previous_item_name = ""
						for item in range(0,len(orders[o][pallet_type][pallet][0])):
							item_name = orders[o][pallet_type][pallet][0][item].attrib["name"]
							print "------> Item "+str(item)+": "+item_name
							if item == 0:
								mission.append("go:empty_pallet")
								mission.append("pick:empty_pallet")

							if item_name != previous_item_name:
								mission.append("go:"+item_name)
								mission.append("pick:"+item_name)
							else:
								mission.append("pick:"+item_name)
							previous_item_name = item_name

				mission.append("go:shipping_area")
				mission.append("drop:pallet")

			mission.append("go:home")
			missions.append(mission)
			mission = []
		return missions

	def parse_orders_times_file(self):
		self.missions_times = []
		with open(self.orders_times_file,"r") as file:
			for line in file:
				self.missions_times.append(int(line))
		print self.missions_times

	def parse_item_locations_file(self):
		with open(self.items_locations_file,"r") as file:
			self.item_locations_data = json.load(file)
		print self.item_locations_data

	def parse_location_coordinates_file(self):
		with open(self.locations_coordinates_file,"r") as file:
			self.location_coordinates_data = json.load(file)

	def start_gui(self):
		#start the self.gui
		self.gui = tk.Tk()
		self.gui.title("ILIAD Goal manager")

		self.files_frame = tk.LabelFrame(self.gui,text="Files Loaded",font=("Arial Bold", 12))
		self.files_frame.grid(row=0,column=0,padx=10, pady=10,sticky="w")

		self.missions_frame = tk.LabelFrame(self.gui,text="Mission Status",font=("Arial Bold", 12))
		self.missions_frame.grid(row=1,column=0,padx=10, pady=10,sticky="w")

		self.robots_frame = tk.LabelFrame(self.gui,text="Robot Status",font=("Arial Bold", 12))
		self.robots_frame.grid(row=2,column=0,padx=10, pady=10,sticky="w")

		#files frame
		orders_label = tk.Label(self.files_frame, text = "Orders: ",font=("Arial Bold", 10))
		orders_times_label = tk.Label(self.files_frame, text = "Orders times: ",font=("Arial Bold", 10)) 
		items_locations_label = tk.Label(self.files_frame, text = "Items locations: ",font=("Arial Bold", 10))
		locations_coordinates_label = tk.Label(self.files_frame, text = "Locations coordinates: ",font=("Arial Bold", 10))
		orders_label.grid(               row=0,column=0,pady=3,padx=5,sticky="e")
		orders_times_label.grid(         row=1,column=0,pady=3,padx=5,sticky="e")
		items_locations_label.grid(      row=2,column=0,pady=3,padx=5,sticky="e")
		locations_coordinates_label.grid(row=3,column=0,pady=3,padx=5,sticky="e")

		orders_text = tk.Label(self.files_frame, text = self.orders_file,font=("Arial Bold", 10),bg="white",width=100)
		orders_times_text = tk.Label(self.files_frame, text = self.orders_times_file,font=("Arial Bold", 10),bg="white",width=100)
		items_locations_text = tk.Label(self.files_frame,       text = self.items_locations_file,font=("Arial Bold", 10),bg="white",width=100)
		locations_coordinates_text = tk.Label(self.files_frame, text = self.locations_coordinates_file,font=("Arial Bold", 10),bg="white",width=100)
		orders_text.grid(row=0,column=1,sticky="w")
		orders_times_text.grid(row=1,column=1,sticky="w")
		items_locations_text.grid(row=2,column=1,sticky="w")
		locations_coordinates_text.grid(row=3,column=1,sticky="w")

		# mission status panel
		available_label = tk.Label(self.missions_frame, text = "Robots available ",font=("Arial Bold", 10),justify="right")
		available_label.grid(row=0,column=0,pady=5,padx=5)

		self.available_list = tk.Listbox(self.missions_frame,width=15,font=("Arial Bold", 10),height=4,justify="center",selectmode="multiple",selectbackground="green")
		self.available_list.grid(row=1,column=0,rowspan=3,padx=5,pady=5)

		self.allow_exploration = tk.IntVar()
		allow_exploration_checkbutton = tk.Checkbutton(self.missions_frame,text="Allow exploration",variable=self.allow_exploration,onvalue=1,offvalue=0)
		allow_exploration_checkbutton.grid(row=4,column=0,padx=5,pady=5)

		start_missions_button = tk.Button(self.missions_frame, text ="Start\nmissions", command = self.start_missions_callback,height=5, width=5,background="green",activebackground="green",font=("Arial Bold", 10))
		start_missions_button.grid(row=1,rowspan=4,column = 1,padx=5)

		progress_label = tk.Label(self.missions_frame, text = "Progress: ",font=("Arial Bold", 10),justify="right")
		completed_label = tk.Label(self.missions_frame, text = "Completed: ",font=("Arial Bold", 10),justify="right")
		queued_label = tk.Label(self.missions_frame, text = "Queued: ",font=("Arial Bold", 10),justify="right")
		next_label =      tk.Label(self.missions_frame, text = "Next: ",font=("Arial Bold", 10),justify="right")
		progress_label.grid(row=1,column=2,sticky="e",pady=3,padx=5)
		completed_label.grid(row=2,column=2,sticky="e",pady=3,padx=5)
		queued_label.grid(row=3,column=2,sticky="e",pady=3,padx=5)
		next_label.grid(     row=4,column=2,sticky="e",pady=3,padx=5)

		self.progress_text_label = tk.Label(self.missions_frame,font=("Arial Bold", 10),bg="white",width = 35)
		self.completed_text_label = tk.Label(self.missions_frame,font=("Arial Bold", 10),bg="white",width = 35)
		self.queued_text_label = tk.Label(self.missions_frame,font=("Arial Bold", 10),bg="white",width = 35)
		self.next_text_label =      tk.Label(self.missions_frame,font=("Arial Bold", 10),bg="white",width = 35)
		self.progress_text_label.grid(row=1,column=3,sticky="w")
		self.completed_text_label.grid(row=2,column=3,sticky="w")
		self.queued_text_label.grid(row=3,column=3,sticky="w")
		self.next_text_label.grid(     row=4,column=3,sticky="w")

		abort_missions_button = tk.Button(self.missions_frame, text ="Abort\nall\nmissions", command = self.abort_missions_callback,height=5, width=5,background="red",activebackground="red",font=("Arial Bold", 10))
		abort_missions_button.grid(row=1,rowspan=4,column = 4,padx=5)

		# robot status panel
		active_label = tk.Label(self.robots_frame, text = "Active",font=("Arial Bold", 10))
		status_label = tk.Label(self.robots_frame, text = "Status",font=("Arial Bold", 10))
		mission_label = tk.Label(self.robots_frame, text = "Mission",font=("Arial Bold", 10))
		navigation_label = tk.Label(self.robots_frame, text = "Navigation",font=("Arial Bold", 10))
		wait_label = tk.Label(self.robots_frame, text = "Wait",font=("Arial Bold", 10))
		goal_label = tk.Label(self.robots_frame, text = "Goal",font=("Arial Bold", 10))
		action_label = tk.Label(self.robots_frame, text = "Action",font=("Arial Bold", 10))
		active_label.grid(row=0,column=0,pady=5,padx=5)
		status_label.grid(row=0,column=1,pady=5,padx=5)
		mission_label.grid(row=0,column=2,pady=5,padx=5)
		navigation_label.grid(row=0,column=3,pady=5,padx=5)
		wait_label.grid(row=0,column=4,pady=5,padx=5)
		goal_label.grid(row=0,column=5,pady=5,padx=5)
		action_label.grid(row=0,column=6,pady=5,padx=5)

		self.active_list = tk.Listbox(self.robots_frame,width=15,font=("Arial Bold", 10),height=4,justify="center")
		self.status_list = tk.Listbox(self.robots_frame,width=6,font=("Arial Bold", 10), height=4,justify="center")
		self.mission_list = tk.Listbox(self.robots_frame,width=7,font=("Arial Bold", 10),height=4,justify="center")
		self.navigation_list = tk.Listbox(self.robots_frame,width=10,font=("Arial Bold", 10),height=4,justify="center")
		self.wait_list = tk.Listbox(self.robots_frame,width=5,font=("Arial Bold", 10),height=4,justify="center")
		self.goal_list = tk.Listbox(self.robots_frame,width=12,font=("Arial Bold", 10),height=4,justify="center")
		self.action_list = tk.Listbox(self.robots_frame,width=30,font=("Arial Bold", 10),height=4,justify="center")
		self.active_list.grid(row=1,column=0,padx=5,pady=5)
		self.status_list.grid(row=1,column=1,padx=5,pady=5)
		self.mission_list.grid(row=1,column=2,padx=5,pady=5)
		self.navigation_list.grid(row=1,column=3,padx=5,pady=5)
		self.wait_list.grid(row=1,column=4,padx=5,pady=5)
		self.goal_list.grid(row=1,column=5,padx=5,pady=5)
		self.action_list.grid(row=1,column=6,padx=5,pady=5)

		skip_goal_button = tk.Button(self.robots_frame, text ="Skip\ncurrent\ngoal", command = self.skip_goal_callback, width=5,background="orange",activebackground="orange",font=("Arial Bold", 10))
		skip_mission_button = tk.Button(self.robots_frame, text ="Skip\ncurrent\nmission", command = self.skip_mission_callback, width=5,background="red",activebackground="red",font=("Arial Bold", 10))
		skip_goal_button.grid(row=1,column = 7,padx=5)
		skip_mission_button.grid(row=1,column = 8,padx=5)

		#self.gui.mainloop() #blocking

	def start_missions_callback(self):
		print "starting the missions"
		if self.missions_started == 0:
			#update the active robots list from the selection
			robot_names = self.available_list.get(0,tk.END)
			robot_selection =  self.available_list.curselection()

			if len(robot_selection) > 0:
				for i in range(0,len(robot_selection)):
					self.active_list.insert(tk.END,robot_names[robot_selection[i]])
					self.active_robots[robot_names[robot_selection[i]]] = {"status":"-","mission":"-","goal":"-","wait":0,"navigation":"-"}

				# make the times relative to the starting time
				current_time = rospy.get_time()
				self.corrected_missions_times = self.missions_times[:]
				for t in range(0,len(self.missions_times)):
					self.corrected_missions_times[t] = self.missions_times[t] + current_time

				self.missions_started = 1

			else:
				tkMessageBox.showwarning("Warning","Select at least 1 robot\nfrom the available list\nto perform the missions")
				return
			
		return

	def abort_missions_callback(self):
		print "aborting all missions"
		if self.missions_started:
			self.available_list_updated = 0
			self.missions_started = 0
			self.available_robots = {}
			self.active_robots = {}
			self.next_mission = 0
			self.queued_missions = []
			self.all_missions_added = 0
			self.completed_missions = []

			# for robot in self.active_robots:
			# 	if self.active_robots[robot_selected]["mission"] != "-":
			# 		self.active_robots[robot_selected]["goal"] = "-"
			# 		self.active_robots[robot_selected]["mission"] = "-"
			# 		self.active_robots[robot_selected]["wait"] = 0


		return

	def skip_goal_callback(self):
		if len(self.active_list.curselection()) > 0:
			robot_names = self.active_list.get(0,tk.END)
			robot_selected  = robot_names[self.active_list.curselection()[0]]
			print "skippin goal in robot: ", robot_selected

			if self.active_robots[robot_selected]["mission"] != "-":
				self.process_new_goal(robot_selected)
		else:
			tkMessageBox.showwarning("Warning","Select at least 1 robot\nfrom the active list")

		return

	def skip_mission_callback(self):
		if len(self.active_list.curselection()) > 0:
			robot_names = self.active_list.get(0,tk.END)
			robot_selected  = robot_names[self.active_list.curselection()[0]]
			print "skippin mission in robot: ", robot_selected
			
			if self.active_robots[robot_selected]["mission"] != "-":
				self.completed_missions.append(self.active_robots[robot_selected]["mission"] )
				self.active_robots[robot_selected]["goal"] = "-"
				self.active_robots[robot_selected]["mission"] = "-"
				self.active_robots[robot_selected]["wait"] = 0
		else:
			tkMessageBox.showwarning("Warning","Select at least 1 robot\nfrom the active list")

		return

	def exploration_goal_callback(self,exploration_goal_msg):
		if self.allow_exploration:
			for robot in self.active_robots:
				if self.active_robots[robot]["status"] == "FREE":
					break
		return

	def fleet_status_callback(self,msg):
		#read message from 
		self.robot_navigation_status = {"robot3":"FREE","robot4":"MOVING","robot5":"FREE"}

		#update the available robot list only at the start
		if self.available_list_updated==0:
			self.available_list.delete(0,tk.END)
			for robot in self.robot_navigation_status:
				self.available_list.insert(tk.END,robot)
			self.available_list_updated = 1

		# update the navigation status of the active robots from the info coming from the coordinator
		if self.missions_started:
			for robot in self.active_robots:
				self.active_robots[robot]["navigation"] = self.robot_navigation_status[robot]

		return

	def assign_missions_and_goals(self,timer):
		if self.missions_started:
			#check if there is any mission queued that can be assigned to a robot
			if len(self.queued_missions) > 0:
				#check if any of the active robots is free
				for robot in self.active_robots:
					if self.active_robots[robot]["status"] == "FREE":
						# assign the mission to the free robot
						self.active_robots[robot]["status"] = "BUSY"
						self.active_robots[robot]["mission"] = self.queued_missions[0]
						del self.queued_missions[0]
			 			break

			# 	#check if the waiting deadline is over for each active robot and the navigation is over
			for robot in self.active_robots:
				if (self.active_robots[robot]["mission"]!= "-" and self.active_robots[robot]["navigation"] == "FREE" and self.active_robots[robot]["wait"]<=rospy.get_time()):
						self.process_new_goal(robot)
			
			#update the general status of the robot based navigation and active mission
			for robot in self.active_robots:
				if (self.active_robots[robot]["navigation"] == "FREE" and self.active_robots[robot]["mission"]=="-"):
					self.active_robots[robot]["status"] = "FREE"
				else:
					self.active_robots[robot]["status"] = "BUSY"

		return

	def process_new_goal(self,robot):
		current_goal = self.active_robots[robot]["goal"]
		current_mission = self.active_robots[robot]["mission"]

		if current_goal == "-":
			new_goal = 0
		else:
			new_goal = current_goal + 1
			if new_goal >= len(self.missions[current_mission]):
				#all goals from this mission completed
				self.active_robots[robot]["goal"] = "-"
				self.active_robots[robot]["mission"] = "-"
				self.active_robots[robot]["wait"] = 0
				self.completed_missions.append(current_mission)
				return

		self.active_robots[robot]["goal"] = new_goal
		# read the new goal
		goal_description = self.missions[int(current_mission)][int(new_goal)]
		goal_description = goal_description.split(":")
		action = goal_description[0]

		if action == "go":
			#send a goal to the coordinator
			item = goal_description[1]

			if item =="home":
				location = self.item_locations_data[item+"_"+robot]
				coordinates = self.location_coordinates_data[location]
				x = coordinates[0]
				y = coordinates[1]
				yaw = coordinates[2]
				print "Coordinates"+str(coordinates)
			else:
				location = self.item_locations_data[item]
				coordinates = self.location_coordinates_data[location]
				x = coordinates[0]
				y = coordinates[1]
				yaw = coordinates[2]
				print "Coordinates"+str(coordinates)

			# now we use a 10 seconds wait instead
			self.active_robots[robot]["wait"] = rospy.get_time() +10

		if action == "pick":
			object = goal_description[1]
			# since there is not actual picking in the sim we use a wait instead
			self.active_robots[robot]["wait"] = rospy.get_time() + 5

		if action == "drop":
			# now we use a 10 seconds wait instead
			self.active_robots[robot]["wait"] = rospy.get_time() + 10

		return

	def gui_update(self):
		current_time = rospy.get_time()

		#update mission panel
		self.progress_text_label.config(text=str(len(self.completed_missions))+"/"+str(len(self.missions))) 
		self.completed_text_label.config(text="Missions " + str(self.completed_missions))
		self.queued_text_label.config(text="Missions " + str(self.queued_missions))
		if self.all_missions_added or self.missions_started==0:
			self.next_text_label.config(text="-")
		else:
			self.next_text_label.config(text="Mission "+str(self.next_mission)+" in "+str(int(self.corrected_missions_times[self.next_mission]-current_time))+" sec")

		#update robot status panel
		self.status_list.delete(0,tk.END)
		self.mission_list.delete(0,tk.END)
		self.goal_list.delete(0,tk.END)
		self.navigation_list.delete(0,tk.END)
		self.wait_list.delete(0,tk.END)
		self.action_list.delete(0,tk.END)
		if len(self.active_robots) > 0:
			for robot in self.active_robots:
				self.status_list.insert(tk.END,self.active_robots[robot]["status"])
				self.mission_list.insert(tk.END,self.active_robots[robot]["mission"])
				self.navigation_list.insert(tk.END,self.active_robots[robot]["navigation"])
				if self.active_robots[robot]["mission"] == "-":
					self.goal_list.insert(tk.END,str(self.active_robots[robot]["goal"]))
				else:
					self.goal_list.insert(tk.END,str(self.active_robots[robot]["goal"])+"/"+str(len(self.missions[int(self.active_robots[robot]["mission"])])))

				if self.active_robots[robot]["mission"] != "-" and self.active_robots[robot]["goal"] != "-":
					self.action_list.insert(tk.END,self.missions[self.active_robots[robot]["mission"]][self.active_robots[robot]["goal"]])
				else:
					self.action_list.insert(tk.END,"-")

				if self.active_robots[robot]["wait"]-current_time >= 0:
					self.wait_list.insert(tk.END,int(self.active_robots[robot]["wait"]-current_time))
				else:
					self.wait_list.insert(tk.END,0)
		else:
			self.active_list.delete(0,tk.END)


		self.gui.update() # non blocking
		
	def run(self):
		r = rospy.Rate(10)
		while not rospy.is_shutdown():

			# the misison are put in the queue when their starting time arrives
			if (self.missions_started==1 and self.all_missions_added==0):
				if self.corrected_missions_times[self.next_mission] <= rospy.get_time():
					self.queued_missions.append(self.next_mission)
					self.next_mission = self.next_mission + 1
					if self.next_mission >= len(self.corrected_missions_times):
						self.all_missions_added = 1

			#update all the gui fields with the new info
			self.gui_update()
			
			# simulating the coordiantor publishing the topic
			self.fleet_status_callback(0)

			# provide info in topics
			self.active_robots_status_pub.publish(json.dumps(self.active_robots))

			self.mission_status["completed"] = self.completed_missions
			self.mission_status["queued"] = self.queued_missions
			if (self.missions_started==1 and self.all_missions_added==0):
				self.mission_status["seconds_left_next"] = int(self.corrected_missions_times[self.next_mission]-rospy.get_time())
			else:
				self.mission_status["seconds_left_next"] = 	"-"
			self.mission_status_pub.publish(json.dumps(self.mission_status))

			r.sleep()


if __name__ == '__main__':
	rospy.init_node('iliad_goal_manager_node', anonymous=True)
	igm = iliad_goal_manager()
