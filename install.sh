#!/bin/bash

# Check if running as root
if [ "$EUID" -ne 0 ]; then 
    echo "Please run as root"
    exit 1
fi

# Create installation directory
install_dir="/opt/broadlink-scheduler"
mkdir -p $install_dir

# Copy project files
cp -r . $install_dir/

# Fix permissions
username=$SUDO_USER
if [ -z "$username" ]; then
    username=$(whoami)
fi

chown -R $username:$username $install_dir
chmod +x $install_dir/scheduler.py

# Update service file with correct username
sed -i "s/YOUR_USERNAME/$username/" broadlink-scheduler.service

# Install systemd service
cp broadlink-scheduler.service /etc/systemd/system/
systemctl daemon-reload
systemctl enable broadlink-scheduler
systemctl start broadlink-scheduler

echo "Installation complete. Service status:"
systemctl status broadlink-scheduler