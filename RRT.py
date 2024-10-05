import ctypes
import os
import time
import win32com.client
import psutil
from ctypes import wintypes

def enable_debug_privilege():
    SE_DEBUG_NAME = "SeDebugPrivilege"
    TOKEN_ADJUST_PRIVILEGES = 0x20
    TOKEN_QUERY = 0x8
    SE_PRIVILEGE_ENABLED = 0x2

    token = wintypes.HANDLE()
    ctypes.windll.advapi32.OpenProcessToken(
        ctypes.windll.kernel32.GetCurrentProcess(),
        TOKEN_ADJUST_PRIVILEGES | TOKEN_QUERY,
        ctypes.byref(token)
    )

    luid = wintypes.LUID()
    ctypes.windll.advapi32.LookupPrivilegeValueW(None, SE_DEBUG_NAME, ctypes.byref(luid))

    class LUID_AND_ATTRIBUTES(ctypes.Structure):
        _fields_ = [("Luid", wintypes.LUID), ("Attributes", wintypes.DWORD)]

    class TOKEN_PRIVILEGES(ctypes.Structure):
        _fields_ = [("PrivilegeCount", wintypes.DWORD), ("Privileges", LUID_AND_ATTRIBUTES * 1)]

    new_privileges = TOKEN_PRIVILEGES()
    new_privileges.PrivilegeCount = 1
    new_privileges.Privileges[0].Luid = luid
    new_privileges.Privileges[0].Attributes = SE_PRIVILEGE_ENABLED

    ctypes.windll.advapi32.AdjustTokenPrivileges(
        token, False, ctypes.byref(new_privileges), 0, None, None
    )

    ctypes.windll.kernel32.CloseHandle(token)
    return ctypes.GetLastError() == 0

def terminate_process_by_name(process_name):
    for process in psutil.process_iter(['pid', 'name']):
        if process.info['name'] == process_name:
            try:
                p = psutil.Process(process.info['pid'])
                p.terminate()
                print(f"[+] Terminated process: {process_name}")
            except:
                pass

def unhook_dll_in_process(process, dll_name):
    path = os.path.join(os.environ['WINDIR'], "System32" if ctypes.sizeof(ctypes.c_voidp) == 8 else "SysWOW64", dll_name)

    dll = ctypes.windll.kernel32.GetModuleHandleW(dll_name)
    if dll:
        module_info = ctypes.create_string_buffer(ctypes.sizeof(ctypes.c_ulonglong))
        if ctypes.windll.psapi.GetModuleInformation(process, dll, ctypes.byref(module_info), ctypes.sizeof(module_info)):
            dll_file = open(path, 'rb')
            dll_file_data = dll_file.read()
            dll_file.close()

            for section in range(module_info):
                section_name = module_info[section]
                if section_name == b'.text':
                    base_address = section.VirtualAddress
                    size = section.Misc.VirtualSize

                    old_protect = ctypes.c_ulong()
                    ctypes.windll.kernel32.VirtualProtectEx(process, base_address, size, 0x40, ctypes.byref(old_protect))

                    ctypes.windll.kernel32.WriteProcessMemory(
                        process, base_address, dll_file_data[base_address:base_address+size], size, None)

                    ctypes.windll.kernel32.VirtualProtectEx(process, base_address, size, old_protect, ctypes.byref(old_protect))

                    print(f"[+] Unhooked {dll_name} at {path}")
                    break

def delete_tasks_with_prefix(prefix):
    service = win32com.client.Dispatch("Schedule.Service")
    service.Connect()
    folder = service.GetFolder("\\")
    tasks = folder.GetTasks(0)

    for task in tasks:
        if task.Name.startswith(prefix):
            folder.DeleteTask(task.Name, 0)
            print(f"[+] Deleted task: {task.Name}")

def main():
    time.sleep(1)

    enable_debug_privilege()

    dlls_to_unhook = ["ntdll.dll", "advapi32.dll", "sechost.dll", "pdh.dll", "amsi.dll"]

    for process in psutil.process_iter(['pid', 'name']):
        process_handle = ctypes.windll.kernel32.OpenProcess(0x1F0FFF, False, process.info['pid'])
        if process.info['name'] == 'dllhost.exe':
            try:
                terminate_process_by_name('dllhost.exe')
            except:
                pass
        else:
            for dll in dlls_to_unhook:
                unhook_dll_in_process(process_handle, dll)

    prefix_to_delete = "$"
    delete_tasks_with_prefix(prefix_to_delete)

    os.system("cls")
    print("Ring3 Rootkit Unhooked!")
    os.system("pause")

if __name__ == "__main__":
    main()
