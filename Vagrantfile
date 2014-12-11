# -*- mode: ruby -*-
# vi: set ft=ruby :

# Vagrantfile API/syntax version. Don't touch unless you know what you're doing!
VAGRANTFILE_API_VERSION = "2"

Vagrant.configure(VAGRANTFILE_API_VERSION) do |config|
  config.vm.box = "ubuntu-14.04"

  config.vm.box_url = "https://cloud-images.ubuntu.com/vagrant/trusty/current/trusty-server-cloudimg-amd64-vagrant-disk1.box"

  config.vm.define "m1" do |mach|
    mach.vm.network :private_network, ip: "10.10.10.10"
  end
  config.vm.define "m2" do |mach|
    mach.vm.network :private_network, ip: "10.10.10.20"
  end
  config.vm.define "m3" do |mach|
    mach.vm.network :private_network, ip: "10.10.10.30"
  end
  config.vm.define "s1" do |mach|
    mach.vm.network :private_network, ip: "10.10.20.10"
  end
#  config.vm.define "s2" do |mach|
#    mach.vm.network :private_network, ip: "10.10.20.20"
#  end
#  config.vm.define "s3" do |mach|
#    mach.vm.network :private_network, ip: "10.10.20.30"
#  end

  config.ssh.forward_agent = true

  # config.vm.synced_folder "../data", "/vagrant_data"

  config.vm.provider "virtualbox" do |vb|
    vb.gui = false

    vb.customize ["modifyvm", :id, "--memory", "512"]
  end

  config.vm.provision "ansible" do |ansible|
    ansible.playbook = "site.yml"

    ansible.groups = {
      "mesos_masters" => ["m1", "m2", "m3"],
      "mesos_slaves" => ["s1", "s2", "s3"],
    }
  end
end
