# -*- mode: ruby -*-
# vi: set ft=ruby :

# ==============================================================================
# DockPilot - Optional All-in-One Linux VM Sandbox
# ==============================================================================
# Provides an isolated Linux environment running Docker Engine, Docker Compose,
# DockPilot Backend (:8001), Prometheus (:9090), Grafana (:3000), Alertmanager (:9093),
# and cAdvisor (:8085).
#
# Resource-conscious defaults designed for 8 GB RAM host systems:
# Default: 2 CPUs, 2048 MB RAM (override via DOCKPILOT_VM_CPUS / DOCKPILOT_VM_MEMORY).
# Does not interfere with Windows Docker Desktop.

Vagrant.configure("2") do |config|
  config.vm.box = "ubuntu/jammy64"
  config.vm.hostname = "dockpilot-sandbox"

  # Port Forwarding from VM to Host
  config.vm.network "forwarded_port", guest: 8001, host: 8001, auto_correct: true, id: "dockpilot"
  config.vm.network "forwarded_port", guest: 9090, host: 9090, auto_correct: true, id: "prometheus"
  config.vm.network "forwarded_port", guest: 3000, host: 3000, auto_correct: true, id: "grafana"
  config.vm.network "forwarded_port", guest: 9093, host: 9093, auto_correct: true, id: "alertmanager"
  config.vm.network "forwarded_port", guest: 8085, host: 8085, auto_correct: true, id: "cadvisor"

  # VirtualBox Provider Settings
  config.vm.provider "virtualbox" do |vb|
    vb.name = "dockpilot-vm"
    vb.cpus = (ENV['DOCKPILOT_VM_CPUS'] || 2).to_i
    vb.memory = (ENV['DOCKPILOT_VM_MEMORY'] || 2048).to_i
    vb.gui = false
    vb.customize ["modifyvm", :id, "--natdnshostresolver1", "on"]
    vb.customize ["modifyvm", :id, "--cableconnected1", "on"]
  end

  # Shared Project Folder
  config.vm.synced_folder ".", "/vagrant", type: "virtualbox", mount_options: ["dmode=775,fmode=664"]

  # Shell Provisioning Script
  config.vm.provision "shell", path: "vagrant/provision.sh"
end
