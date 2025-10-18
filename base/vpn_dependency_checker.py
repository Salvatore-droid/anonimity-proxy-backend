# vpn_dependency_checker.py
import subprocess
import sys

def check_vpn_dependencies():
    """Check if all VPN dependencies are installed"""
    print("🔧 Checking VPN dependencies...")
    
    dependencies = {
        'openvpn': 'OpenVPN',
        'wg-quick': 'WireGuard',
        'ssh': 'SSH'
    }
    
    all_installed = True
    
    for cmd, name in dependencies.items():
        try:
            result = subprocess.run([cmd, '--version'], 
                                  capture_output=True, text=True, timeout=5)
            if result.returncode == 0:
                print(f"✅ {name} is installed")
            else:
                print(f"❌ {name} is NOT installed properly")
                all_installed = False
        except FileNotFoundError:
            print(f"❌ {name} is NOT installed")
            all_installed = False
        except subprocess.TimeoutExpired:
            print(f"⚠️  {name} check timed out")
        except Exception as e:
            print(f"⚠️  Error checking {name}: {e}")
    
    if not all_installed:
        print("\n🚨 MISSING DEPENDENCIES DETECTED!")
        print("💡 Installation commands:")
        print("   Ubuntu/Debian: sudo apt install openvpn wireguard-tools openssh-client")
        print("   CentOS/RHEL: sudo yum install openvpn wireguard-tools openssh-clients")
        return False
    
    print("🎉 All VPN dependencies are installed and ready!")
    return True

if __name__ == "__main__":
    check_vpn_dependencies()