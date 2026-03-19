# -*- mode: ruby -*-
# vi: set ft=ruby :

Vagrant.configure("2") do |config|
  # 1. 镜像选择：使用最稳定的 Ubuntu 24.04 (Noble)
  config.vm.box = "bento/ubuntu-24.04"

  # 2. 网络配置：
  # 设置私有 IP，你可以直接在 Windows 浏览器访问这个地址
  config.vm.network "private_network", ip: "192.168.56.10"
  
  # 端口转发：将虚拟机的 8000 端口映射到物理机的 8000 端口
  # 这样你访问 localhost:8000 也能打开你的 Django/Flask 项目
  config.vm.network "forwarded_port", guest: 8000, host: 8000

  # 3. 目录同步：
  # 将当前目录（Windows 项目文件夹）映射到虚拟机的 /home/vagrant/app
  config.vm.synced_folder ".", "/home/vagrant/app", 
    type: "virtualbox",
    owner: "vagrant",
    group: "vagrant"

  # 4. 虚拟机硬件优化：
  config.vm.provider "virtualbox" do |vb|
    vb.name = "Python_Web_Dev_VM"
    vb.memory = "2048" # 内存分配 2GB
    vb.cpus = 2        # 核心分配 2核
    # 提升性能的设置
    vb.customize ["modifyvm", :id, "--natdnshostresolver1", "on"]
  end

  # 5. 自动配置脚本 (Provisioning)：
  # 第一次启动时会自动执行这些命令，帮你装好 Python 环境
  config.vm.provision "shell", inline: <<-SHELL
    # 更新系统并安装 Python 相关工具
    export DEBIAN_FRONTEND=noninteractive
    apt-get update
    apt-get install -y python3 python3-pip python3-venv git build-essential libpq-dev

    # 进入项目目录并创建 Python 虚拟环境
    cd /home/vagrant/app
    python3 -m venv .venv
    chown -R vagrant:vagrant .venv

    echo "===================================================="
    echo "环境搭建完成！"
    echo "虚拟机 IP: 192.168.56.10"
    echo "代码目录: /home/vagrant/app"
    echo "请运行 'vagrant ssh' 进入系统，然后执行 'source .venv/bin/activate'"
    echo "===================================================="
  SHELL
end