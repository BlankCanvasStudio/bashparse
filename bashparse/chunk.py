import bashparse, copy


# This could be an interesting idea
def visit_children(nodes, function):
    pass


class Chunk:
    def __init__(self, variable_name, start, end):
        self.name = variable_name 
        self.start = start
        self.end = end
    def __repr__(self):
        start = end = "None"
        if self.start: start = '[' + ','.join(str(x) for x in self.start) + ']'
        if self.end: end = '[' + ','.join(str(x) for x in self.end) + ']'
        return "Chunk(" + self.name + ', ' + start + ', ' + end + ')'
    def __str__(self):
        start = end = "None"
        if self.start: start = '[' + ','.join(str(x) for x in self.start) + ']'
        if self.end: end = '[' + ','.join(str(x) for x in self.end) + ']'
        return "Chunk(" + self.name + ', ' + start + ', ' + end + ')'
    

class chunk_connection:
    def __init__(self, chunk, connected_to):
        self.chunk = chunk
        self.connected_to = connected_to
    def __repr__(self):
        return "chunk_connection(chunk: " + str(self.chunk) +' connected to: ' + str(self.connected_to) + ')'
    def __str__(self):
        return "chunk_connection(chunk: " + str(self.chunk) +' connected to: ' + str(self.connected_to) + ')'


def are_variables_involved(nodes):
    if type(nodes) != list: nodes = [nodes]
    for i in range(0, len(nodes)):
        if nodes[i].kind == 'assignment': return True
        if nodes[i].kind == 'parameter': return True
        # Don't need to check if lower uses vars, if it is confirmed in upper
        if hasattr(nodes[i], 'parts'): 
            for part in nodes[i].parts:
                result = are_variables_involved(part)
                if result: return result
        if hasattr(nodes[i], 'list'):
            for part in nodes[i].list:
                result = are_variables_involved(part)
                if result: return result
        if hasattr(nodes[i], 'command'):  # some nodes are just pass through nodes
            result = are_variables_involved(part)
            if result: return result
        if hasattr(nodes[i], 'output'):   # some nodes are just pass through nodes
            result = are_variables_involved(part)
            if result: return result
    return False


def return_variable_commands(nodes):
    to_return = []
    for node in nodes:
        if are_variables_involved(node):
            to_return += [copy.deepcopy(node)]
    return to_return


def find_variable_chunks(nodes):
    if type(nodes) is not list: nodes = [nodes]
    chunks = {}
    for i, node in enumerate(nodes):
        assignments = bashparse.return_paths_to_node_type(node, 'assignment')
        evaluations = bashparse.return_variable_paths(node)

        for assignment in assignments:
            name = assignment.node.word.split('=')[0]
            if name not in chunks: chunks[name] = []
            chunks[name] += [Chunk(name, [i] + assignment.path, [i] + assignment.path)]
            # chunks[name] += [Chunk(name, [i], None)]

        for evaluation in evaluations:
            name = evaluation.node.value
            j = 0
            while name in chunks and j < len(chunks[name]):
                if chunks[name][j].start > [i] + evaluation.path: break
                j += 1

            if j >= 0 and name in chunks: 
                chunks[name][j - 1].end = [i] + evaluation.path
            elif j < 0: raise ValueError('finding the chunk went negative. idk how')
    return chunks


def find_cd_chunks(nodes):
    # This needs to be improved to take functions into account?
    if type(nodes) is not list: nodes = [nodes]
    chunks = []
    # Retieve all the cd commands
    commands = bashparse.return_paths_to_node_type(nodes, 'command')
    cds = []
    for command in commands: 
        if hasattr(command.node.parts[0], 'word') and command.node.parts[0].word == 'cd': cds += [ command ]
    # Build the chunks based off the cd commands found 
    i = 0
    while i < len(cds):
        chunk_start = cds[i].path
        
        # If the cds are right next to one another then we are going to increment the chunks cause chained cds should be in the same chunk
        test = True
        while test and i + 1 < len(cds):

            if len(cds[i].path) == 1 and len(cds[i+1].path) == 1 and cds[i].path[0] + 1 == cds[i+1].path[0]: i += 1
            elif len(cds[i].path) == 2 and len(cds[i+1].path) == 2 and cds[i].path[0] + 1 == cds[i+1].path[0]: i += 1
                # Idk if this ^^ Is really good or necessary when its unrolled
            elif cds[i].path[-1] == cds[i+1].path[-1] + 1 and cds[i].path[:-1] == cds[i+1].path[:-1]: i += 1
            else: test = False
            
        # Set the value of the end of the chunk
        if len(cds) > i + 1:  # If there is another cd between current location and EOF
            if cds[i+1].path[-1] > 0: chunk_end =  cds[i+1].path[:-1] +  [ cds[i+1].path[-1] - 1 ]
            else: chunk_end = cds[i+1].path[:-2] + [cds[i+1].path[-2] - 1] + [ 0 ]
        else:  # If there isn't a cd as the last line then set the final chunk to the nodes from last cd to end of file
            chunk_end = [ len(nodes) - 1 ]  # [ len(nodes) - 1, 0 ]  
        
        chunks += [Chunk('cd', chunk_start, chunk_end)]
        i += 1
    return chunks
        
        
def is_connected(is_chunk, connected_chunk):
    if connected_chunk.start[0] < is_chunk.start[0] and connected_chunk.end[0]: return True 
    if connected_chunk.start[0] < is_chunk.end[0] and connected_chunk.end[0]: return True
    return False


def return_connected_chunks(chunks):
    variable_names = list(chunks.keys())
    # Check every key we have in dict
    connected_chunks = []
    for i, name in enumerate(variable_names):
        variable_chunks = chunks[name]
        # Check every chunk we have associated with a given key
        for chunk in variable_chunks:
            # Check that chunk vs all chunks associated with every following key (meaning its a 100% compared)
            for j_name in variable_names[i+1:]:
                for j_chunk in chunks[j_name]:
                    if is_connected(chunk, j_chunk):
                        connected_chunks += [chunk_connection(chunk, j_chunk)]
    return connected_chunks


def var_is_used_in_declaration(assignment_node, var_name):
    variables = bashparse.return_nodes_of_type(assignment_node, 'parameter')
    for var in variables: 
        if var.value == var_name: return True
    return False


def return_dependent_chunks(connected_chunks, orig_nodes):
    # 4 dependencies: nested in same chunk, cd(?), used in the same line, used in definition, $2 acts on results of $1 command
    dependent_chunks = []
    for chunk in connected_chunks:
        # Used in variable definition
        assignments = bashparse.return_paths_to_node_type(orig_nodes, 'assignment')
        for assignment in assignments:
            if assignment.path > chunk.chunk.start: # This might break with the introduction of cd as first entry
                is_dependent = False
                if assignment.node.word.split('=')[0] == chunk.chunk.name: is_dependent = var_is_used_in_declaration(assignment.node, chunk.connected_to.name)
                if assignment.node.word.split('=')[0] == chunk.connected_to.name: is_dependent = var_is_used_in_declaration(assignment.node, chunk.chunk.name)
                if is_dependent:
                    dependent_chunks += [ chunk ]
                    break
    
    return dependent_chunks


def easy_nuclear_slicing(nodes):
    if type(node) is not list: nodes = [nodes]

    chunks = []

    for i in range(0, len(nodes)):
        for j in range(i+1, len(nodes)):
            chunks += [ Chunk(start=i, end=j) ]

    return chunks

def search_engine_slicing_method(nodes):

    chunks = []
    
    # Do Stuff

    return chunks



def run_identify_chunks(nodes):
    return identify_variable_chunks(nodes)


def identify_variable_chunks(nodes):
    # This is just going to grab chunk indexes based on the variable locations
    chunks = []
    assignment_chunks = bashtemplate.chunk.find_variable_chunks(nodes)
    for key in assignment_chunks.keys():
        # Strip out just the chunks. Don't care about the variables involved
        chunks += assignment_chunks[key]
    # connected_chunks = return_connected_chunks(assignment_chunks)
    # dependent_chunks = return_dependent_chunks(connected_chunks, nodes)
    # chunks += assignment_chunks
    cd_chunks = bashtemplate.chunk.find_cd_chunks(nodes)
    chunks += cd_chunks
    
    return chunks






# filename="testing.sh"

# nodes = bashparse.parse(open(filename).read())

# variable_assignments = bashparse.return_nodes_of_type(nodes, 'assignment')

# variable_uses = bashparse.return_variable_paths(nodes)

# variable_commands = return_variable_commands(nodes)

# chunks = find_variable_chunks(nodes)

# connected_chunks = return_connected_chunks(chunks)

# dependent_chunks = return_dependent_chunks(connected_chunks, nodes)

# print('dependent chunks: ')
# for chunk in dependent_chunks:
#     print(chunk)
