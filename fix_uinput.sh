#!/bin/bash
# Create tmpfiles.d config to persist permissions across reboots
echo 'z /dev/uinput 0660 root uinput' > /etc/tmpfiles.d/dictator-uinput.conf

# Apply now
chgrp uinput /dev/uinput
chmod 660 /dev/uinput

echo "Done! Permissions will persist after reboot."
