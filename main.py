#!/usr/bin/env python3
# Author: Jonas, ChainLayer

import json, subprocess, platform, os, socket, getpass
from contextlib import closing
from sys import exit
from progress.bar import ChargingBar


# Get user input
def get_user_data():
    global keystore_password
    keystore_password = getpass.getpass(prompt='[+] Please enter your keystore password: ')

    global consensus_node
    consensus_node = input('[+] Please enter IP address of a consensus node (testnet/mainnet): ')

    global consensus_node_port
    consensus_node_port = input('[+] Please enter RPC port of the consensus node: ')
    
# Determine which ethdo binary to use (Linux / Darwin)
def determine_os():
    global ethdo_binary
    global ethdo_base_dir

    try:
        operating_system = platform.system()
        print("\u001b[32m[+] Found operating system:\t %s" % (operating_system))

        if operating_system.lower() == "darwin":
            ethdo_binary = "./ethdo/darwin/ethdo"
            print("\u001b[32m[+] Using the ethdo binary for:\t Darwin")

        elif operating_system.lower() == "linux":
            ethdo_binary = "./ethdo/linux/ethdo"
            print("\u001b[32m[+] Using the ethdo binary for:\t Linux")
        
        ethdo_base_dir = "--base-dir=wallets"
        
    except Exception as e:
        print(e)

def check_consensus_connection():
    with closing(socket.socket(socket.AF_INET, socket.SOCK_STREAM)) as sock:
        sock.settimeout(5)
        if sock.connect_ex((str(consensus_node), int(consensus_node_port))) == 0:
            print("\u001b[32m[+] Connected to consensus node %s on port %s" % (consensus_node, consensus_node_port))
        else:
            print("\u001b[33m[+] Could not connect to consensus node %s on port %s. Exiting..." % (consensus_node, consensus_node_port))
            exit()

# Generate offline preparation data from consensus node
def offline_preparation():
    print("\u001b[33m[+] Starting to prepare offline data from consensus node. This might take a while...")
    try:
        cmd = "%s --connection http://%s:%s validator exit --prepare-offline --allow-insecure-connections --timeout 10m" % (ethdo_binary, consensus_node, consensus_node_port)
        print("\u001b[33m[+] Running command: " + cmd)
        subprocess.run(cmd, shell=True,  capture_output=True)
        print("\u001b[32m[+] Network state fetched")

    except Exception as e:
        print(e)

def count_loaded_keystores():
    dir_path = "./data/input/"
    total_files = 0
    for path in os.listdir(dir_path):
        if os.path.isfile(os.path.join(dir_path, path)):
            if path.startswith("keystore"):
                total_files += 1
    print("\u001b[32m[+] Loaded %s keystores for processing" % total_files)
    return total_files

# Create temporary wallet that is located in the wallets folder.
def create_wallet():
    cmd = "%s --base-dir=wallets wallet create --wallet=wallet" % (ethdo_binary)
    subprocess.run(cmd, shell=True,  capture_output=True)

# Add key/account to wallet from keystore file.
def add_key_from_keystore(file):
    cmd = "%s %s account import --account=wallet/account --keystore=./data/input/%s --keystore-passphrase='%s' --passphrase=pass --allow-weak-passphrases --timeout 10m" % (ethdo_binary, ethdo_base_dir, file, keystore_password)
    subprocess.run(cmd, shell=True)

# Generate and sign exit messages to use in the ejector.
def generate_and_sign_exit_messages(pubKey): 
    cmd = "%s %s validator exit --account=wallet/account --passphrase=pass --json --verbose --offline --allow-weak-passphrases --timeout 10m" % (ethdo_binary, ethdo_base_dir)
    result = subprocess.run(cmd, shell=True, capture_output=True)
    with open("./data/output/" + pubKey + '.json', 'w') as f:
        f.write(result.stdout.decode())

# Clean up wallets
def cleanup_wallets():
    try:
        cmd = "%s %s wallet delete --wallet=wallet" % (ethdo_binary, ethdo_base_dir)
        subprocess.run(cmd, shell=True)

    except Exception as e:
        print(e)

def cleanup_offline_preparation_data():
    try:
        cmd = "rm offline-preparation.json"
        subprocess.run(cmd, shell=True)
    except Exception as e:
        print(e)

def main():
    total_loaded_keys = count_loaded_keystores() 
    get_user_data()
    check_consensus_connection()
    determine_os()
    #offline_preparation()
    print("\u001b[33m[+] Starting to create wallets, adding keys from keystores and generating pre-signed messages")
    keystores_count = 0
    with ChargingBar('[+] Processing keystores', max=total_loaded_keys) as bar:
        for i in range(total_loaded_keys):
            for file in os.listdir("./data/input"):
                if file.startswith("keystore"):
                    create_wallet()
                    with open("./data/input/" + file, 'r') as f:
                        result = json.load(f)
                        pubKey = "0x" + result["pubkey"]
                    add_key_from_keystore(file)
                    generate_and_sign_exit_messages(pubKey)
                    cleanup_wallets()
                    keystores_count += 1
                    bar.next()
        bar.finish()
    
    print("\u001b[32m[+] Successfully created pre-signed messages for %d keystores, check your output folder" % (keystores_count))
    print("\u001b[31m[+] Remember to clean your input/output folders.")
    cleanup_offline_preparation_data()

if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print('[+] User aborted.')
