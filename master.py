import hashlib
import json
from time import time
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse
from uuid import uuid4

import requests
from flask import Flask, jsonify, request
import keys
import validation


class Blockchain:
	def __init__(self):
		self.current_transactions = []
		self.chain = []
		self.nodes = set()

		# Create the genesis block
		self.new_block(previous_hash='1', proof=100)

	def register_node(self, address: str) -> None:
		"""
		Add a new node to the list of nodes

		:param address: Address of node. Eg. 'http://192.168.0.5:5000'
		"""

		parsed_url = urlparse(address)
		self.nodes.add(parsed_url.netloc)

	def valid_chain(self, chain: List[Dict[str, Any]]) -> bool:
		"""
		Determine if a given blockchain is valid

		:param chain: A blockchain
		:return: True if valid, False if not
		"""

		last_block = chain[0]
		current_index = 1

		while current_index < len(chain):
			block = chain[current_index]
			print(f'{last_block}')
			print(f'{block}')
			print("\n-----------\n")
			# Check that the hash of the block is correct
			if block['previous_hash'] != self.hash(last_block):
				return False

			# Check that the Proof of Work is correct
			if not self.valid_proof(last_block['proof'], block['proof']):
				return False

			last_block = block
			current_index += 1

		return True

	def resolve_conflicts(self) -> bool:
		"""
		This is our consensus algorithm, it resolves conflicts
		by replacing our chain with the longest one in the network.

		:return: True if our chain was replaced, False if not
		"""

		neighbours = self.nodes
		new_chain = None

		# We're only looking for chains longer than ours
		max_length = len(self.chain)

		print('Length of our chain is {}'.format(max_length))


		# Grab and verify the chains from all the nodes in our network
		for node in neighbours:
			print(node)

			response = requests.get('http://{}/chain'.format(node))
			print(response.url)
			print(response.ok)

			if response.status_code == 200:
				print('Response code status = 200')
				length = response.json()['length']
				chain = response.json()['chain']

				print('length : {}, chain: {}'.format(length, chain))

				# Check if the length is longer and the chain is valid
				if length > max_length and self.valid_chain(chain):
					max_length = length
					new_chain = chain
					print ('Chain updated')

		# Replace our chain if we discovered a new, valid chain longer than ours
		if new_chain:
			self.chain = new_chain
			return True

		return False

	def new_block(self, proof: int, previous_hash=None):
		"""
		Create a new Block in the Blockchain

		:param proof: The proof given by the Proof of Work algorithm
		:param previous_hash: Hash of previous Block
		:return: New Block
		"""

		block = {
			'index': len(self.chain) + 1,
			'timestamp': time(),
			'transactions': self.current_transactions,
			'proof': proof,
			'previous_hash': previous_hash or self.hash(self.chain[-1]),
		}

		# Reset the current list of transactions
		self.current_transactions = []

		self.chain.append(block)
		return block

	def new_transaction(self, sender: str, recipient: str, amount: int) -> int:
		"""
		Creates a new transaction to go into the next mined Block

		:param sender: Address of the Sender
		:param recipient: Address of the Recipient
		:param amount: Amount
		:return: The index of the Block that will hold this transaction
		"""
		self.current_transactions.append({
			'sender': sender,
			'recipient': recipient,
			'amount': amount,
		})

		return self.last_block['index'] + 1

	def get_balance(self, pkey):
		consensus()

		add = 0
		sub = 0

		for block in self.chain:

			for transaction in block['transactions']:
				if transaction['recipient'] == pkey:
					add += transaction['amount']
					# print('add = {}'.format(add))

				if transaction['sender'] == pkey:
					sub += transaction['amount']
					# print('sub = {}'.format(sub))

			# print('net: {}'.format(add-sub))

		return add-sub

	@property
	# def last_block(self) -> Dict[str: Any]:
	def last_block(self):
		return self.chain[-1]

	@staticmethod
	def hash(block: Dict[str, Any]) -> str:
		"""
		Creates a SHA-256 hash of a Block

		:param block: Block
		"""

		# We must make sure that the Dictionary is Ordered, or we'll have inconsistent hashes
		block_string = json.dumps(block, sort_keys=True).encode()
		return hashlib.sha256(block_string).hexdigest()

	def proof_of_work(self, last_proof: int) -> int:
		"""
		Simple Proof of Work Algorithm:
		 - Find a number p' such that hash(pp') contains leading 4 zeroes, where p is the previous p'
		 - p is the previous proof, and p' is the new proof
		"""

		proof = 0
		while self.valid_proof(last_proof, proof) is False:
			proof += 1

		return proof

	@staticmethod
	def valid_proof(last_proof: int, proof: int) -> bool:
		"""
		Validates the Proof

		:param last_proof: Previous Proof
		:param proof: Current Proof
		:return: True if correct, False if not.
		"""

		guess = f'{last_proof}{proof}'.encode()
		guess_hash = hashlib.sha256(guess).hexdigest()
		return guess_hash[:4] == "0000"


# Instantiate the Node
app = Flask(__name__)

# Generate a globally unique address for this node
node_identifier = str(uuid4()).replace('-', '')
# node_identifier = '1PSXQuHixWq9RL1xHDd23wKmBsWG3Fadmh'

# Instantiate the Blockchain
blockchain = Blockchain()


@app.route('/generate', methods=['GET'])
def generate():
	# generate private & public key pair using keys.py
	response = keys.gen_add()

	return jsonify(response), 200



@app.route('/mine', methods=['GET'])
def mine():
	# We run the proof of work algorithm to get the next proof...
	last_block = blockchain.last_block
	last_proof = last_block['proof']
	proof = blockchain.proof_of_work(last_proof)

	# We must receive a reward for finding the proof.
	# The sender is "0" to signify that this node has mined a new coin.
	blockchain.new_transaction(
		sender="0",
		recipient=node_identifier,
		amount=1,
	)

	# Forge the new Block by adding it to the chain
	block = blockchain.new_block(proof)

	response = {
		'message': "New Block Forged",
		'index': block['index'],
		'transactions': block['transactions'],
		'proof': block['proof'],
		'previous_hash': block['previous_hash'],
	}
	return jsonify(response), 200

@app.route('/getbalance', methods=['POST'])
def get_balance():
	values = request.get_json()

	# Check that the required fields are in the POST'ed data
	required = ['pkey']
	if not all(k in values for k in required):
		return 'Missing values', 400

	balance = blockchain.get_balance(values['pkey'])

	response = {'balance' : balance}

	return jsonify(response), 201



@app.route('/transactions/new', methods=['POST'])
def new_transaction():
	values = request.get_json()

	# Check that the required fields are in the POST'ed data
	required = ['sender', 'pkey', 'recipient', 'amount']
	if not all(k in values for k in required):
		return 'Missing values', 400

	balance = blockchain.get_balance(values['sender'])

	# Verify that accounts are valid and private & public key pair are valid and acc has enough funds
	if validation.check_bc(values['sender']) and validation.check_bc(values['recipient']) and keys.check_key(values['sender'], values['pkey']) and balance >= values['amount']:
		# Create a new Transaction
		index = blockchain.new_transaction(values['sender'], values['recipient'], values['amount'])

		response = {'message': f'Transaction will be added to Block {index}'}
		return jsonify(response), 201

	response = 'Addresses/ Private key are not valid.'
	return jsonify(response), 400



@app.route('/chain', methods=['GET'])
def full_chain():
	response = {
		'chain': blockchain.chain,
		'length': len(blockchain.chain),
	}
	return jsonify(response), 200


@app.route('/nodes/register', methods=['POST'])
def register_nodes():
	values = request.get_json()

	nodes = values.get('nodes')
	if nodes is None:
		return "Error: Please supply a valid list of nodes", 400

	for node in nodes:
		blockchain.register_node(node)

	response = {
		'message': 'New nodes have been added',
		'total_nodes': list(blockchain.nodes),
	}
	return jsonify(response), 201


@app.route('/nodes/resolve', methods=['GET'])
def consensus():
	replaced = blockchain.resolve_conflicts()

	if replaced:
		response = {
			'message': 'Our chain was replaced',
			'new_chain': blockchain.chain
		}
	else:
		response = {
			'message': 'Our chain is authoritative',
			'chain': blockchain.chain
		}

	return jsonify(response), 200


if __name__ == '__main__':
	from argparse import ArgumentParser

	parser = ArgumentParser()
	parser.add_argument('-p', '--port', default=5000, type=int, help='port to listen on')
	args = parser.parse_args()
	port = args.port

	app.run(host='0.0.0.0', port=port, debug=True)
