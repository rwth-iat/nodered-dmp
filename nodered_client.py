#!/usr/bin/env python3
import json
import uuid

from abc import ABC # Abstract Base Class

class NodeBase(ABC):
    """
    Base class for all objects.
    Each object has a unique id and a type.
    """

    def __init__(self, node_type, **kwargs):
        self.id = kwargs.get("id", str(uuid.uuid4().hex[:16]))
        self.type = node_type
        self.properties = kwargs  # additional properties for the object
        self.internal_properties = {} # properties only for use in this code. Will not be included in the JSON output.

    def to_dict(self):
        """
        Return a dictionary representation of the node,
        including its id, type, properties, and wires (if any).
        """
        node_dict = {"id": self.id, "type": self.type}
        # Include all other properties except id and type
        for key, value in self.properties.items():
            if key not in ["id", "type"]: # TODO: If yes, handle with exception
                node_dict[key] = value
        return node_dict
    

class Node(NodeBase):
    """
    Base class for all nodes.
    Each node has a unique id, a type, properties (as a dict) and wires.
    Wires are represented as a list of lists, where each sublist represents one output.
    """

    def __init__(self, node_type, **kwargs):
        super().__init__(node_type, **kwargs)
        self.wires = []  # list of lists for output wires

    def add_wire(self, target_node, output_index=0):
        """
        Connect this node to a target node on a given output.
        The wires property is a list of lists (to support multiple outputs).
        """
        while len(self.wires) <= output_index:
            self.wires.append([])
        self.wires[output_index].append(target_node.id)
    
    def to_dict(self):
        """
        Return a dictionary representation of the node,
        including its id, type, properties, and wires (if any).
        """
        node_dict = super().to_dict()
        if self.wires:
            node_dict["wires"] = self.wires
        return node_dict

class ConfigNode(NodeBase):
    """
    A node used for configuration (e.g. servers, brokers).
    Inherits from Node.
    """

    def __init__(self, node_type, **kwargs):
        super().__init__(node_type, **kwargs)


class MQTTBroker(ConfigNode):
    """
    Represents a MQTT broker configuration node.
    Loads default configuration from a JSON file ('mqtt_broker_defaults.json') and
    allows overwriting some of its elements via the constructor.
    """

    def __init__(self, name, broker, port=1883, **kwargs):
        # Load default configuration from the JSON file.
        with open("mqtt_broker_defaults.json", "r") as f:
            defaults = json.load(f)

        # Overwrite the defaults with the user-supplied parameters.
        defaults["name"] = name
        defaults["broker"] = broker
        defaults["port"] = port
        defaults.update(kwargs)

        # Initialize the configuration node with type "mqtt-broker" using merged properties.
        super().__init__("mqtt-broker", **defaults)


class MQTTIn(Node):
    """
    Represents a Node-RED MQTT input node.
    """

    def __init__(self, topic, qos="2", broker="", **kwargs):
        super().__init__("mqtt in", topic=topic, qos=qos, broker=broker, **kwargs)


class HTTPRequest(Node):
    """
    Represents an HTTP request node.
    """

    def __init__(self, method="GET", url="", **kwargs):
        super().__init__("http request", method=method, url=url, **kwargs)

class Change(Node):
    """
    Represents a Node-RED change node.
    """

    def __init__(self, rules, **kwargs):
        # rules is a list of dictionaries defining the change rules, chekc it if it is, if not, make it a list
        if not isinstance(rules, list):
            rules = [rules]
        super().__init__("change", rules=rules, **kwargs)

class Function(Node):
    """
    Represents a Node-RED function node.
    """

    def __init__(self, func, **kwargs):
        super().__init__("function", func=func, **kwargs)

class Json(Node):
    """
    Represents a Node-RED JSON node.
    """

    def __init__(self, action="", **kwargs):
        # action is a string, either "", "str" or "obj"
        if action not in ["", "str", "obj"]:
            raise ValueError("Invalid action for JSON node. Must be '', 'str', or 'obj'.")
        super().__init__("json", action=action, **kwargs)
        
class Flow:
    """
    Main class for building a Node-RED flow.
    It automatically creates a 'tab' node and lets you add other nodes and define
    connections between them.

    In addition, it maintains a grid layout:
    - The x positions for each column are provided as a list when the flow is created.
    - Offsets (for x and y) and vertical spacing are configurable.
    - When adding a node, an optional 'column' index can be provided; if so, the node's
      "x" and "y" properties are set automatically to the next free position in that column.
    """

    default_name = "Flow"
    instance_counter = 0  # Class variable to track number of instances


    def __init__(self, name=None, count_number=None, columns=None, x_offset=0, y_offset=140, vertical_spacing=80):
        # Create the tab node that represents the flow
        cls = type(self)  # the actual class being instantiated
        
        # Count he number of instances of this class
        # ensure the class has its own counter attribute
        if not hasattr(cls, 'instance_counter'):
            cls.instance_counter = 0

        if count_number is not None:
            # user-supplied override
            self.instance_number = count_number
            # bump the class counter if needed
            if count_number >= cls.instance_counter:
                cls.instance_counter = count_number + 1
        else:
            # auto-assign the next number
            cls.instance_counter += 1
            self.instance_number = cls.instance_counter
        
        instance_name = "{} {}".format(cls.default_name, self.instance_number)
        if name is None:
            name = instance_name
        elif name == "":
            name = instance_name


        self.base_data = {"id": str(uuid.uuid4().hex[:16])}

        if type(self) is Flow:
            self.base_data_update = {
                "type": "tab",
                "label": name,
                "disabled": False,
                "info": "",
                "env": []
            }
        elif type(self) is Subflow:
            self.base_data_update["name"] = name
        
        
        self.base_data.update(self.base_data_update)
        self.nodes = [self.base_data]
        self.node_lookup = {}

        # Grid layout settings:
        # A list of x positions for each column.
        self.columns = columns if columns is not None else [210, 850]
        self.x_offset = x_offset
        self.y_offset = y_offset
        self.vertical_spacing = vertical_spacing
        # Dictionary to keep track of the last y position in each column.
        # Keys are column indices, values are the last used y coordinate.
        self.last_positions = {}

    def add_node(self, node, column=None):
        """
        Add a node (instance of Node or its subclass) to the flow.
        If 'column' is provided, the node's "x" and "y" properties are set to the next free
        position in that column based on the grid settings.
        Also, if the node does not have a 'z' property, it is automatically assigned the flow's tab id.
        Returns the id of the added node.
        """
        # TODO: Allow update/modification of nodes, which are already addet to the flow.
        # Assign the flow id if not already set.
        if "z" not in node.properties and node.type not in ["mqtt-broker"]:
            node.properties["z"] = self.base_data["id"]

        # TODO: encapsulate this part in a function for possible reuse also in add_ghost_node
        # If a column is specified, compute and set the x and y coordinates.
        if column is not None:
            if column < 0 or column >= len(self.columns):
                raise ValueError("Column index out of range. Available columns: 0 to {}.".format(len(self.columns) - 1))
            # Set x position from the column vector plus offset.
            node.properties["x"] = self.columns[column] + self.x_offset
            # Determine y position: if no node exists yet in this column, start with y_offset.
            if column in self.last_positions:
                y = self.last_positions[column] + self.vertical_spacing
            else:
                y = self.y_offset
            node.properties["y"] = y
            # Update the last y position for this column.
            self.last_positions[column] = y

        node_dict = node.to_dict()
        self.nodes.append(node_dict)
        self.node_lookup[node.id] = node
        return node.id
    
    def add_ghost_node(self, column):
        pass

    def add_subflow(self, subflow):
        """
        Add a subflow to the flow. This is a special case where the subflow
        is added as a node in the flow.
        """
        if not isinstance(subflow, Subflow):
            raise ValueError("Only Subflow instances can be added.")
        self.nodes.extend(subflow.nodes)
        self.node_lookup[subflow.base_data["id"]] = subflow
        return subflow.base_data["id"]
    
    def get_node(self, node_id):
        """
        Retrieve a node by its ID.
        """
        if node_id in self.node_lookup:
            return self.node_lookup[node_id]
        else:
            raise ValueError("Node with ID {} not found.".format(node_id))
        
    def connect_nodes(self, source_node, target_node, output_index=0):
        """
        Connect the source node to the target node.
        This updates the source node's wires both in its object and in the flow list.
        """
        if source_node.id not in self.node_lookup or target_node.id not in self.node_lookup:
            raise ValueError("Both nodes must be added to the flow before connecting.")
        source_node.add_wire(target_node, output_index)
        # Update the corresponding node dictionary in the nodes list.
        for node in self.nodes:
            if node["id"] == source_node.id:
                node["wires"] = source_node.wires
                break


        
    def remove_node(self, node_id):
        """
        Remove a node from the flow by its ID.
        """
        if node_id in self.node_lookup:
            node = self.node_lookup[node_id]
            # Remove the node from the nodes list
            self.nodes = [n for n in self.nodes if n["id"] != node_id]
            # Remove the node from the lookup dictionary
            del self.node_lookup[node_id]
            # Also remove any wires connected to this node
            for n in self.nodes:
                if "wires" in n and isinstance(n["wires"], list):
                    n["wires"] = [w for w in n["wires"] if w != node_id]
        else:
            raise ValueError("Node with ID {} not found.".format(node_id))
 

    def generate_json(self):
        """
        Generate and return the JSON representation of the flow.
        """
        return json.dumps(self.nodes, indent=4)

class Subflow(Flow):
    """
    Represents a Node-RED subflow that can be added to flows or other subflows.
    It behaves similar to a Flow but creates a subflow node that can be referenced
    by other flows using the get_instance() method.
    """

    default_name = "Subflow"
    instance_counter = 0

    def __init__(self, name=None, count_number=None, columns=None, x_offset=0, y_offset=140, vertical_spacing=80):
        # Create the subflow node instead of a tab node

        self.base_data_update = {
            "type": "subflow",
            "info": "",
            "category": "",
            "in": [], # TODO solve placement of in and out nodes
            "out": [], # 
            "env": [],
            "meta": {},
            "color": "#DDAA99"
        }
        super().__init__(name=name, count_number=count_number, columns=columns, x_offset=x_offset, y_offset=y_offset, vertical_spacing=vertical_spacing)
    
    def add_node(self, node, column=None):
        """
        Add a node to the subflow. In subflows, nodes must have a "z" property
        that references the subflow ID rather than a tab ID.
        """
        # Assign the subflow id if not already set
        if "z" not in node.properties:
            node.properties["z"] = self.base_data["id"]
        
        # Continue with the standard node addition logic
        return super().add_node(node, column)
    
    def get_instance(self):
        """
        Returns a SubflowInstance node that can be added to flows or other subflows.
        This is the node that references this subflow and can be used in a flow.
        """
        instance = Node("subflow:" + self.base_data["id"])
        return instance
    
    def connect_to_input(self, target_nodes):
        """
        Connect the subflow input node to one or more target nodes.
        This is useful for defining the starting point of the subflow's internal logic.
        
        Parameters:
            target_nodes: A Node instance or a list of Node instances
        """
        # Convert single node to a list for consistent handling
        if not isinstance(target_nodes, list):
            target_nodes = [target_nodes]
        
        for target_node in target_nodes:
            if target_node.id not in self.node_lookup:
                raise ValueError("Target node must be added to the subflow before connecting.")
            # Create the input node if it doesn't exist, only one can be created
            if len(self.base_data["in"]) == 0:
                # Create input node
                self.base_data["in"].append({"x": self.x_offset, "y": self.y_offset, "wires": []})
            # Connect subflow input to the target node
            self.base_data["in"][0]["wires"].append({"id":target_node.id})
            
        # Update the tab node in the nodes list
        for idx, node in enumerate(self.nodes):
            if node["id"] == self.base_data["id"]:
                self.nodes[idx] = self.base_data
                break
        
    def connect_to_output(self, source_node, output_index=0, output_interface_number=1):
        """
        Connect the source node to the subflow output node.
        This is useful for defining the end point of the subflow's internal logic.
        
        Parameters:
            source_node: A Node instance
            output_index: The index of the output wire to connect to
            output_interface_number: The interface number for the output
        """
        if source_node.id not in self.node_lookup:
            raise ValueError("Source node must be added to the subflow before connecting.")
        # Create the output node if it doesn't exist, create so many as needed
        while len(self.base_data["out"]) < output_interface_number:
            # TODO: solve default x position
            self.base_data["out"].append({"x": self.x_offset + 1000, "y": self.y_offset + (len(self.base_data["out"]) * self.vertical_spacing), "wires": []})
        # Connect the source node to the subflow output
        self.base_data["out"][output_interface_number-1]["wires"].append({"id":source_node.id, "port":output_index})
        
        # Update the tab node in the nodes list
        for idx, node in enumerate(self.nodes):
            if node["id"] == self.base_data["id"]:
                self.nodes[idx] = self.base_data
                break

            


# ---------------- Example usage ----------------
if __name__ == "__main__":
    # Create a new flow with default grid settings.
    flow = Flow("Flow 1", columns=[210, 850], x_offset=0, y_offset=140, vertical_spacing=80)

    # Add MQTT broker configuration nodes (they don't need grid positions).
    mqtt_broker_1 = MQTTBroker(name="MQTT_Server_1", broker="mqtt-broker", port=1883)
    flow.add_node(mqtt_broker_1)
    mqtt_broker_2 = MQTTBroker(name="", broker="localhost", port=1883)
    flow.add_node(mqtt_broker_2)

    # Add nodes with automatic grid positioning.
    # Nodes in column 0 will be placed along the first column (x=210) and nodes in column 1 along x=850.
    mqtt_in_1 = MQTTIn(topic="test1", qos="2", broker=mqtt_broker_1.id)
    flow.add_node(mqtt_in_1, column=0)
    http_req_1 = HTTPRequest(method="GET", url="")
    flow.add_node(http_req_1, column=1)
    flow.connect_nodes(mqtt_in_1, http_req_1)

    mqtt_in_2 = MQTTIn(topic="test2", qos="2", broker=mqtt_broker_1.id)
    flow.add_node(mqtt_in_2, column=0)
    http_req_2 = HTTPRequest(method="GET", url="")
    flow.add_node(http_req_2, column=1)
    flow.connect_nodes(mqtt_in_2, http_req_2)

    mqtt_in_3 = MQTTIn(topic="test3", qos="2", broker=mqtt_broker_1.id)
    flow.add_node(mqtt_in_3, column=0)
    http_req_3 = HTTPRequest(method="GET", url="")
    flow.add_node(http_req_3, column=1)
    flow.connect_nodes(mqtt_in_3, http_req_3)

    # Add an MQTT input node for topic 'test440' using the second MQTT broker in column 0.
    mqtt_in_4 = MQTTIn(topic="test440", qos="2", broker=mqtt_broker_2.id)
    flow.add_node(mqtt_in_4, column=0)

# Example of creating the requested subflow
    # Create a new subflow
    subflow = Subflow(name="Subflow 1", count_number=1, columns=[10, 390, 520], x_offset=100, y_offset=140, vertical_spacing=80)
    
    # Create the HTTP request node
    http_req = HTTPRequest(
        name="get", 
        method="GET", 
        ret="txt",
        paytoqs="ignore", 
        url="http://aas-env:8081/submodels/aHR0cHM6Ly9leGFtcGxlLmNvbS9pZHMvc20vT3BlcmF0aW9uYWxEYXRh/submodel-elements/MQTT_Data.voltage",
        persist=False,
        insecureHTTPParser=False,
        senderr=False,
        headers=[]
    )
    subflow.add_node(http_req, column=1)  # x=390, y=80
    http_req.properties["y"] = 80  # Override y position
    
    # Create the join node
    join_node = Node(
        "join",
        name="",
        mode="custom",
        build="object",
        property="payload",
        propertyType="msg",
        key="topic",
        joiner="\\n",
        joinerType="str",
        useparts=False,
        accumulate=False,
        timeout="",
        count="2",
        reduceRight=False,
        reduceExp="",
        reduceInit="",
        reduceInitType="",
        reduceFixup=""
    )
    subflow.add_node(join_node, column=1)  # x=390, y=140
    
    # Create the function node
    function_node = Node(
        "function",
        name="function 4",
        func="\nlet jsonData = JSON.parse(msg.payload.json);\nvar updateValue = msg.payload.update;\n\n// Update the desired field\njsonData.value = updateValue;\n\nmsg.payload = jsonData;\nreturn msg;\n",
        outputs=1,
        timeout=0,
        noerr=0,
        initialize="",
        finalize="",
        libs=[]
    )
    subflow.add_node(function_node, column=2)  # x=520, y=140
    
    # Create the change node
    change_node = Node(
        "change",
        name="change",
        rules=[
            {
                "t": "set",
                "p": "topic",
                "pt": "msg",
                "to": "json",
                "tot": "str"
            }
        ],
        action="",
        property="",
        to="",
        reg=False
    )
    subflow.add_node(change_node, column=2)  # x=520, y=80
    change_node.properties["y"] = 80  # Override y position
    
    # Connect the nodes within the subflow
    subflow.connect_nodes(http_req, change_node)
    subflow.connect_nodes(change_node, join_node)
    subflow.connect_nodes(join_node, function_node)
    
    # Connect the subflow input to both http_req and join_node
    subflow.connect_to_input([http_req, join_node])
    
    # Connect function_node to the subflow output
    subflow.connect_to_output(function_node)
    
    flow.add_subflow(subflow)  # Add the subflow to the main flow    
    
    # Get a subflow instance that can be added to the main flow
    subflow_instance = subflow.get_instance()
    flow.add_node(subflow_instance, column=1)
    
    # Now you could connect other nodes to/from the subflow instance
    # Example (if you had other nodes):
    mqtt_in = MQTTIn(topic="input/topic", qos="2")
    flow.add_node(mqtt_in, column=0)
    flow.connect_nodes(mqtt_in, subflow_instance)
    
    # Generate and print the JSON flow.
    print(flow.generate_json())
