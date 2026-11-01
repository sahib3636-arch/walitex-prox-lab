#!/usr/bin/env python3
"""Build an in-place successor to the exact linked mf9mic APK.

Inputs are anchored to the APK the user installed and linked, not a repackaged/recreated app. The
update retains package/name/permissions, uses that release's signing key/lineage, and increments
versionCode by one. Depending on diagnostic flags, it changes the manifest, three dex files, and/or
one verified arm64 native instruction in the original liblitex.so.

Patches in this candidate:
  * classes12 / LX.Pyx.A02: on non-Pixel devices, ignore the 0x34b3 recorder-source override and
    select AudioSource.CAMCORDER (5). The earlier source-5 edits affected only the Pixel 2 XL
    branch; this is the first patch that changes the S24 Ultra branch.
  * classes14 / Listener$Switch: disable Android view-state saving on the six LiteX privacy toggles
    so Activity hierarchy restoration cannot overwrite the SharedPreferences-backed state.
  * classes14 / PrmHandler.getPrm: preserve the two verified Boolean values and supply a one-year
    String display value for 55503. Earlier attempts to unlock the calls switch this way failed.
  * classes14 / WaResources.getBoolean: replace the misbehaving native preference read with the
    equivalent Android SharedPreferences API; the emulator showed native reads disagreeing with
    values written to litex_prefs.xml.
  * classes14 / WaResources.getAlertDialog: optionally log the Java stack and return a standard
    AlertDialog.Builder, while leaving the native switch callback intact. This traces the actual
    Premium-dialog caller; it is diagnostic-only and must not ship.
  * classes14 / Extra.setPrmBanner: optionally suppress this dialog-producing callback for a local
    feature test. This does not by itself prove that the paid feature works and is diagnostic-only.
  * lib/arm64-v8a/liblitex.so: after candidate 408 traced the calls-toggle callback writing the
    requested value and then overwriting it with false, optionally NOP the verified false-argument
    store at VA 0x6ff60. This preserves the first requested boolean in the JNI argument buffer; the
    branch and native callback otherwise remain intact. This is a narrow, diagnostic-gated patch.
  * classes6: let the normal view-once-open/read-receipt path run even when Anti View Once is on,
    while leaving the anti-view-once retention/display code intact.

Every DEX code edit is a one-code-unit binary change with DEX SHA-1/Adler32 repair; classes14 is
reassembled because it needs small Java helpers. The optional native edit is guarded by exact ELF,
VA-to-file-offset, and Capstone instruction checks. Hardware mic capture, real call blocking, and
sender-side receipt visibility still require a real linked-device test.
"""
from __future__ import annotations
import hashlib
import json
import os
import shutil
import struct
import subprocess
import sys
import time
import zipfile
import zlib
from pathlib import Path
from capstone import Cs, CS_ARCH_ARM64, CS_MODE_ARM

ROOT = Path(os.environ.get('PROX_ROOT', str(Path.home())))
PKGDIR = Path(os.environ.get('PROX_BUILD_DIR', str(ROOT / 'prox-build')))
SRC = Path(os.environ.get('PROX_BASE_APK', str(PKGDIR / 'incoming' / 'mf9mic-signed.apk')))
WORK = PKGDIR / 'update-work'
TARGET_VERSION = int(os.environ.get('TARGET_VERSION', '264207412'))
OUT = PKGDIR / 'artifacts' / f'walitex-mf9mic-update-{TARGET_VERSION}.apk'
REPORT = PKGDIR / 'report' / f'update-{TARGET_VERSION}.json'
DIAG_TOGGLE = os.environ.get('PROX_DIAG_TOGGLE', '0') == '1'
TRACE_DIALOGS = os.environ.get('PROX_TRACE_DIALOGS', '0') == '1'
SUPPRESS_PRM_BANNER = os.environ.get('PROX_SUPPRESS_PRM_BANNER', '0') == '1'
DIAG_SET_BOOLEAN = os.environ.get('PROX_DIAG_SET_BOOLEAN', '0') == '1'
DIAG_GET_PRM = os.environ.get('PROX_DIAG_GET_PRM', '0') == '1'
PATCH_PREMIUM_SWITCH_RESET = os.environ.get('PROX_PATCH_PREMIUM_SWITCH_RESET', '0') == '1'
SMALI_CP = ':'.join(f'/usr/share/java/{j}.jar' for j in
                    ('baksmali','smali','dexlib2','smali-util','guava'))
API_LEVEL = '23'

sys.path.insert(0, str(Path(__file__).resolve().parent))
import mic_patch
import build_apk
from axml import Axml


HELPER = '''
.method private static disablePrivacySwitchSaving(Ljava/lang/Object;Ljava/lang/Object;)V
    .registers 8

    instance-of v0, p0, Landroid/app/Activity;
    if-eqz v0, :done

    instance-of v0, p1, Ljava/lang/String;
    if-eqz v0, :done

    check-cast p0, Landroid/app/Activity;
    check-cast p1, Ljava/lang/String;

    const-string v0, "walitex_hide_seen"
    invoke-virtual {p1, v0}, Ljava/lang/String;->equals(Ljava/lang/Object;)Z
    move-result v0
    if-eqz v0, :key1
    const-string v1, "walitex_hide_seen_switch"
    goto :resolve

    :key1
    const-string v0, "walitex_hide_fwd_check"
    invoke-virtual {p1, v0}, Ljava/lang/String;->equals(Ljava/lang/Object;)Z
    move-result v0
    if-eqz v0, :key2
    const-string v1, "walitex_hide_fwd_switch"
    goto :resolve

    :key2
    const-string v0, "hide_statusV2"
    invoke-virtual {p1, v0}, Ljava/lang/String;->equals(Ljava/lang/Object;)Z
    move-result v0
    if-eqz v0, :key3
    const-string v1, "walitex_hide_statusV2_switch"
    goto :resolve

    :key3
    const-string v0, "Antirevoke"
    invoke-virtual {p1, v0}, Ljava/lang/String;->equals(Ljava/lang/Object;)Z
    move-result v0
    if-eqz v0, :key4
    const-string v1, "walitex_antirevoke_switch"
    goto :resolve

    :key4
    const-string v0, "Antirevoke_status_v2"
    invoke-virtual {p1, v0}, Ljava/lang/String;->equals(Ljava/lang/Object;)Z
    move-result v0
    if-eqz v0, :key5
    const-string v1, "walitex_antirevoke_status_v2_switch"
    goto :resolve

    :key5
    const-string v0, "walitex_block_calls_check"
    invoke-virtual {p1, v0}, Ljava/lang/String;->equals(Ljava/lang/Object;)Z
    move-result v0
    if-eqz v0, :done
    const-string v1, "walitex_priv_calls_switch"

    :resolve
    const-string v2, "id"
    invoke-static {p0, v1, v2}, Llitex/WaResources;->getResInt(Landroid/content/Context;Ljava/lang/String;Ljava/lang/String;)I
    move-result v3

    invoke-virtual {p0, v3}, Landroid/app/Activity;->findViewById(I)Landroid/view/View;
    move-result-object v4
    if-eqz v4, :done

    const/4 v5, 0x0
    invoke-virtual {v4, v5}, Landroid/view/View;->setSaveEnabled(Z)V

    :done
    return-void
.end method
'''

P06_NEW = '''.method public static getPrm(I)Ljava/lang/Object;
    .registers 2

    const v0, 0xd8cf
    if-eq p0, v0, :expiry

    const v0, 0xd8cd
    if-eq p0, v0, :premium

    const v0, 0xd8ce
    if-eq p0, v0, :premium

    const/4 v0, 0x0
    return-object v0

    :premium
    sget-object v0, Ljava/lang/Boolean;->TRUE:Ljava/lang/Boolean;
    return-object v0

    :expiry
    const-string v0, "365"
    return-object v0
.end method'''

P06_DIAG_NEW = '''.method public static getPrm(I)Ljava/lang/Object;
    .registers 4

    invoke-static {p0}, Ljava/lang/Integer;->toString(I)Ljava/lang/String;
    move-result-object v1
    const-string v0, "ProXGetPrm"
    invoke-static {v0, v1}, Landroid/util/Log;->i(Ljava/lang/String;Ljava/lang/String;)I
    move-result v2

    const v0, 0xd8cf
    if-eq p0, v0, :expiry

    const v0, 0xd8cd
    if-eq p0, v0, :premium

    const v0, 0xd8ce
    if-eq p0, v0, :premium

    const/4 v0, 0x0
    return-object v0

    :premium
    sget-object v0, Ljava/lang/Boolean;->TRUE:Ljava/lang/Boolean;
    return-object v0

    :expiry
    const-string v0, "365"
    return-object v0
.end method'''

SET_BOOLEAN_DIAG = '''.method public static setBoolean(Ljava/lang/String;Z)V
    .registers 8

    new-instance v0, Ljava/lang/StringBuilder;
    invoke-direct {v0}, Ljava/lang/StringBuilder;-><init>()V
    invoke-virtual {v0, p0}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;
    move-result-object v0
    const-string v1, "="
    invoke-virtual {v0, v1}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;
    move-result-object v0
    invoke-virtual {v0, p1}, Ljava/lang/StringBuilder;->append(Z)Ljava/lang/StringBuilder;
    move-result-object v0
    invoke-virtual {v0}, Ljava/lang/StringBuilder;->toString()Ljava/lang/String;
    move-result-object v0
    const-string v1, "ProXSetBoolean"
    invoke-static {v1, v0}, Landroid/util/Log;->i(Ljava/lang/String;Ljava/lang/String;)I
    move-result v2

    invoke-static {}, Llitex/WaResources;->getSharedPreferences()Landroid/content/SharedPreferences;
    move-result-object v3
    if-eqz v3, :done
    invoke-interface {v3}, Landroid/content/SharedPreferences;->edit()Landroid/content/SharedPreferences$Editor;
    move-result-object v3
    invoke-interface {v3, p0, p1}, Landroid/content/SharedPreferences$Editor;->putBoolean(Ljava/lang/String;Z)Landroid/content/SharedPreferences$Editor;
    move-result-object v3
    invoke-interface {v3}, Landroid/content/SharedPreferences$Editor;->apply()V

    :done
    return-void
.end method'''

GET_ALERT_DIALOG_DIAG = '''.method public static getAlertDialog(Landroid/content/Context;)Landroid/app/AlertDialog$Builder;
    .registers 6

    new-instance v0, Ljava/lang/Exception;
    const-string v1, "WaResources.getAlertDialog diagnostic trace"
    invoke-direct {v0, v1}, Ljava/lang/Exception;-><init>(Ljava/lang/String;)V
    invoke-static {v0}, Landroid/util/Log;->getStackTraceString(Ljava/lang/Throwable;)Ljava/lang/String;
    move-result-object v0
    const-string v1, "ProXDialogTrace"
    invoke-static {v1, v0}, Landroid/util/Log;->i(Ljava/lang/String;Ljava/lang/String;)I
    move-result v2

    new-instance v3, Landroid/app/AlertDialog$Builder;
    invoke-direct {v3, p0}, Landroid/app/AlertDialog$Builder;-><init>(Landroid/content/Context;)V
    return-object v3
.end method'''

SUPPRESS_PRM_BANNER_METHOD = '''.method public static setPrmBanner(Landroid/content/Context;Landroidx/appcompat/widget/SwitchCompat;)V
    .registers 4

    const-string v0, "ProXSetPrmBanner"
    const-string v1, "premium banner suppressed for local feature test"
    invoke-static {v0, v1}, Landroid/util/Log;->i(Ljava/lang/String;Ljava/lang/String;)I
    move-result v2
    return-void
.end method'''

GET_BOOLEAN_FIXED = '''.method public static getBoolean(Ljava/lang/String;Z)Z
    .registers 3

    invoke-static {}, Llitex/WaResources;->getSharedPreferences()Landroid/content/SharedPreferences;
    move-result-object v0
    if-eqz v0, :fallback

    invoke-interface {v0, p0, p1}, Landroid/content/SharedPreferences;->getBoolean(Ljava/lang/String;Z)Z
    move-result v0
    return v0

    :fallback
    return p1
.end method'''

GET_BOOLEAN_DIAG = '''.method public static getBoolean(Ljava/lang/String;Z)Z
    .registers 7

    invoke-static {}, Llitex/WaResources;->getSharedPreferences()Landroid/content/SharedPreferences;
    move-result-object v0
    if-eqz v0, :fallback

    invoke-interface {v0, p0, p1}, Landroid/content/SharedPreferences;->getBoolean(Ljava/lang/String;Z)Z
    move-result v1
    goto :log_value

    :fallback
    move v1, p1

    :log_value
    new-instance v2, Ljava/lang/StringBuilder;
    invoke-direct {v2}, Ljava/lang/StringBuilder;-><init>()V
    invoke-virtual {v2, p0}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;
    move-result-object v2
    const-string v3, "="
    invoke-virtual {v2, v3}, Ljava/lang/StringBuilder;->append(Ljava/lang/String;)Ljava/lang/StringBuilder;
    move-result-object v2
    invoke-virtual {v2, v1}, Ljava/lang/StringBuilder;->append(Z)Ljava/lang/StringBuilder;
    move-result-object v2
    invoke-virtual {v2}, Ljava/lang/StringBuilder;->toString()Ljava/lang/String;
    move-result-object v2
    const-string v3, "ProXToggleRead"
    invoke-static {v3, v2}, Landroid/util/Log;->i(Ljava/lang/String;Ljava/lang/String;)I
    move-result v4
    return v1
.end method'''


def run(argv, cwd=None):
    p = subprocess.run(argv, cwd=cwd, text=True, capture_output=True)
    if p.returncode:
        raise RuntimeError(f"command failed: {' '.join(map(str,argv))}\n{p.stdout[-3000:]}\n{p.stderr[-3000:]}")
    return p.stdout


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def fix_dex(data):
    b = bytearray(data)
    b[12:32] = hashlib.sha1(bytes(b[32:])).digest()
    struct.pack_into('<I', b, 8, zlib.adler32(bytes(b[12:])) & 0xffffffff)
    return bytes(b)


def patch_code_unit(data, cls, meth, code_unit, expected, replacement, label):
    hdr = mic_patch.header(data)
    hits = mic_patch.find_method(data, hdr, cls, meth)
    if len(hits) != 1:
        raise RuntimeError(f'{label}: expected one {cls}->{meth}, found {len(hits)}')
    code_off, insns_off, insns_size = hits[0]
    if not (0 <= code_unit < insns_size):
        raise RuntimeError(f'{label}: code unit {code_unit:#x} outside method ({insns_size:#x})')
    off = insns_off + 2 * code_unit
    old = struct.unpack_from('<H', data, off)[0]
    if old != expected:
        raise RuntimeError(f'{label}: expected instruction {expected:#06x} at {off:#x}, got {old:#06x}')
    b = bytearray(data)
    struct.pack_into('<H', b, off, replacement)
    out = fix_dex(b)
    # Only the one instruction plus the 20-byte SHA-1 and 4-byte Adler32 fields may differ.
    changes = [i for i,(x,y) in enumerate(zip(data,out)) if x != y]
    code_changes = [i for i in changes if not (8 <= i < 32)]
    if code_changes != [off] and code_changes != [off, off+1]:
        raise RuntimeError(f'{label}: unexpected changed code bytes {code_changes[:12]}')
    return out, dict(label=label, class_name=cls, method=meth, code_unit=hex(code_unit),
                     file_offset=hex(off), old=hex(old), new=hex(replacement), code_off=hex(code_off))


def patch_many(data, patches):
    report=[]
    out=data
    for args in patches:
        out, info = patch_code_unit(out, *args)
        report.append(info)
    return out, report


def _elf64_load_offset(data, va):
    if len(data) < 64 or data[:4] != b'\x7fELF' or data[4] != 2 or data[5] != 1:
        raise RuntimeError('liblitex.so is not a little-endian ELF64 object')
    machine = struct.unpack_from('<H', data, 18)[0]
    if machine != 183:
        raise RuntimeError(f'liblitex.so is not AArch64 (e_machine={machine})')
    phoff = struct.unpack_from('<Q', data, 32)[0]
    phentsize = struct.unpack_from('<H', data, 54)[0]
    phnum = struct.unpack_from('<H', data, 56)[0]
    if phentsize < 56 or phoff + phentsize * phnum > len(data):
        raise RuntimeError('liblitex.so has invalid ELF64 program headers')
    for i in range(phnum):
        p_type, p_flags, p_offset, p_vaddr, _, p_filesz, _, _ = struct.unpack_from(
            '<IIQQQQQQ', data, phoff + i * phentsize)
        if p_type == 1 and p_flags & 1 and p_vaddr <= va < p_vaddr + p_filesz:
            return p_offset + va - p_vaddr
    raise RuntimeError(f'VA {va:#x} is not covered by an executable PT_LOAD file range')


def _native_instruction(data, va):
    off = _elf64_load_offset(data, va)
    insns = list(Cs(CS_ARCH_ARM64, CS_MODE_ARM).disasm(data[off:off+4], va))
    if len(insns) != 1 or insns[0].address != va or insns[0].size != 4:
        raise RuntimeError(f'cannot decode one AArch64 instruction at VA {va:#x}')
    return off, insns[0]


def patch_premium_switch_reset(data):
    # This is the exact two-write sequence observed in candidate 408. The first JNI write carries
    # the requested checked value; later, the callback rewrites the same jvalue slot with zero.
    # NOPing only the latter store leaves the original requested value in place for the second write.
    sentinel_va = 0x6fe08
    reset_va = 0x6ff60
    _, sentinel = _native_instruction(data, sentinel_va)
    if (sentinel.mnemonic, sentinel.op_str) != ('sturb', 'w21, [x29, #-0x28]'):
        raise RuntimeError(f'unexpected first switch-value store at {sentinel_va:#x}: '
                           f'{sentinel.mnemonic} {sentinel.op_str}')
    off, old = _native_instruction(data, reset_va)
    if (old.mnemonic, old.op_str) != ('sturb', 'wzr, [x29, #-0x28]'):
        raise RuntimeError(f'unexpected premium reset store at {reset_va:#x}: '
                           f'{old.mnemonic} {old.op_str}')
    _, call = _native_instruction(data, reset_va + 4)
    if (call.mnemonic, call.op_str) != ('blr', 'x8'):
        raise RuntimeError(f'unexpected instruction after reset store: {call.mnemonic} {call.op_str}')
    patched = bytearray(data)
    struct.pack_into('<I', patched, off, 0xd503201f)  # AArch64 NOP
    out = bytes(patched)
    _, new = _native_instruction(out, reset_va)
    if (new.mnemonic, new.op_str) != ('nop', ''):
        raise RuntimeError('native premium-reset patch did not disassemble to NOP')
    changes = [i for i, (a, b) in enumerate(zip(data, out)) if a != b]
    if len(out) != len(data) or any(not (off <= i < off + 4) for i in changes):
        raise RuntimeError(f'native patch changed bytes outside one instruction: {changes[:12]}')
    return out, dict(label='preserve requested calls-switch boolean across native premium reset',
                     va=hex(reset_va), file_offset=hex(off),
                     old=f'{old.mnemonic} {old.op_str}', new=f'{new.mnemonic}',
                     preserved_value_va=hex(sentinel_va), sentinel=f'{sentinel.mnemonic} {sentinel.op_str}',
                     changed_file_bytes=[hex(i) for i in changes])


def check_code_unit(data, cls, meth, code_unit, expected, label):
    hits = mic_patch.find_method(data, mic_patch.header(data), cls, meth)
    if len(hits) != 1:
        raise RuntimeError(f'{label}: expected one {cls}->{meth}, found {len(hits)}')
    _, insns_off, insns_size = hits[0]
    if code_unit >= insns_size:
        raise RuntimeError(f'{label}: code unit {code_unit:#x} outside method')
    off = insns_off + 2 * code_unit
    actual = struct.unpack_from('<H', data, off)[0]
    if actual != expected:
        raise RuntimeError(f'{label}: expected {expected:#06x} at {off:#x}, got {actual:#06x}')
    return dict(label=label, class_name=cls, method=meth, code_unit=hex(code_unit),
                file_offset=hex(off), instruction=hex(actual))


def patch_classes14(dex_path, out_path):
    smali_dir = WORK / 'smali14'
    if smali_dir.exists():
        shutil.rmtree(smali_dir)
    smali_dir.mkdir(parents=True)
    run(['java','-Xmx800m','-cp',SMALI_CP,'org.jf.baksmali.Main','d',str(dex_path),'-o',str(smali_dir)])

    prm = smali_dir / 'litex' / 'prm' / 'PrmHandler.smali'
    text = prm.read_text()
    start = text.index('.method public static getPrm(I)Ljava/lang/Object;')
    end = text.index('.end method', start) + len('.end method')
    old_method = text[start:end]
    if '0xd8cd' not in old_method or '0xd8ce' not in old_method or 'Boolean;->TRUE' not in old_method:
        raise RuntimeError('PrmHandler.getPrm no longer matches the verified P06 base')
    get_prm_method = P06_DIAG_NEW if DIAG_GET_PRM else P06_NEW
    text = text[:start] + get_prm_method + text[end:]
    prm.write_text(text)

    switch = smali_dir / 'litex' / 'bridge' / 'Listener$Switch.smali'
    text = switch.read_text()
    native_case = '.method public static native onCheckedCase22(Ljava/lang/Object;Ljava/lang/Object;Ljava/lang/Object;ZZ)V\n.end method'
    if text.count(native_case) != 1:
        raise RuntimeError('Listener$Switch.onCheckedCase22 native anchor missing')
    # Keep the native callback untouched. The previous replacement did not resolve the Premium UI.
    marker = '.method public constructor <init>(Ljava/lang/Object;Ljava/lang/Object;I)V'
    start = text.index(marker)
    end = text.index('.end method', start)
    block = text[start:end]
    if 'disablePrivacySwitchSaving' in text:
        raise RuntimeError('privacy state helper already exists; refusing duplicate patch')
    anchor = '    iput p3, p0, Llitex/bridge/Listener$Switch;->I:I\n'
    if block.count(anchor) != 1:
        raise RuntimeError('3-argument Listener$Switch constructor changed')
    block = block.replace(anchor, anchor + '\n    invoke-static {p1, p2}, Llitex/bridge/Listener$Switch;->disablePrivacySwitchSaving(Ljava/lang/Object;Ljava/lang/Object;)V\n', 1)
    text = text[:start] + block + text[end:]

    marker4 = '.method public constructor <init>(Ljava/lang/Object;Ljava/lang/Object;Ljava/lang/Object;I)V'
    start4 = text.index(marker4)
    end4 = text.index('.end method', start4)
    block4 = text[start4:end4]
    anchor4 = '    iput p4, p0, Llitex/bridge/Listener$Switch;->I:I\n'
    if block4.count(anchor4) != 1:
        raise RuntimeError('4-argument Listener$Switch constructor changed')
    block4 = block4.replace(anchor4, anchor4 + '\n    invoke-static {p1, p2}, Llitex/bridge/Listener$Switch;->disablePrivacySwitchSaving(Ljava/lang/Object;Ljava/lang/Object;)V\n', 1)
    text = text[:start4] + block4 + text[end4:]
    helper_text = HELPER
    extra = smali_dir / 'litex' / 'bridge' / 'Extra.smali'
    etxt = extra.read_text()
    old_banner = '.method public static native setPrmBanner(Landroid/content/Context;Landroidx/appcompat/widget/SwitchCompat;)V\n.end method'
    if etxt.count(old_banner) != 1:
        raise RuntimeError('Extra.setPrmBanner native anchor missing')
    if SUPPRESS_PRM_BANNER:
        etxt = etxt.replace(old_banner, SUPPRESS_PRM_BANNER_METHOD, 1)
    extra.write_text(etxt)

    wa = smali_dir / 'litex' / 'WaResources.smali'
    wtxt = wa.read_text()
    old_dialog = '.method public static native getAlertDialog(Landroid/content/Context;)Landroid/app/AlertDialog$Builder;\n.end method'
    if wtxt.count(old_dialog) != 1:
        raise RuntimeError('WaResources.getAlertDialog native anchor missing')
    if TRACE_DIALOGS:
        wtxt = wtxt.replace(old_dialog, GET_ALERT_DIALOG_DIAG, 1)
    old_set = '.method public static native setBoolean(Ljava/lang/String;Z)V\n.end method'
    if wtxt.count(old_set) != 1:
        raise RuntimeError('WaResources.setBoolean native anchor missing')
    if DIAG_SET_BOOLEAN:
        wtxt = wtxt.replace(old_set, SET_BOOLEAN_DIAG, 1)
    old_get = '.method public static native getBoolean(Ljava/lang/String;Z)Z\n.end method'
    if wtxt.count(old_get) != 1:
        raise RuntimeError('WaResources.getBoolean native anchor missing')
    wtxt = wtxt.replace(old_get, GET_BOOLEAN_FIXED, 1)
    if DIAG_TOGGLE:
        anchor_log = '    invoke-virtual {v4, v5}, Landroid/view/View;->setSaveEnabled(Z)V\n'
        log_code = ('\n    const-string v5, "ProXSwitchState"\n'
                    '    invoke-static {v5, p1}, Landroid/util/Log;->i(Ljava/lang/String;Ljava/lang/String;)I\n'
                    '    move-result v5\n')
        if helper_text.count(anchor_log) != 1:
            raise RuntimeError('diagnostic switch-state log anchor missing')
        helper_text = helper_text.replace(anchor_log, anchor_log + log_code, 1)
        if wtxt.count(GET_BOOLEAN_FIXED) != 1:
            raise RuntimeError('diagnostic getBoolean replacement anchor missing')
        wtxt = wtxt.replace(GET_BOOLEAN_FIXED, GET_BOOLEAN_DIAG, 1)
    wa.write_text(wtxt)
    text = text.rstrip() + helper_text + '\n'
    switch.write_text(text)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    out_path.unlink(missing_ok=True)
    run(['java','-Xmx800m','-cp',SMALI_CP,'org.jf.smali.Main','a',str(smali_dir),'-o',str(out_path),'--api',API_LEVEL])

    check_dir = WORK / 'check14'
    if check_dir.exists(): shutil.rmtree(check_dir)
    check_dir.mkdir(parents=True)
    run(['java','-Xmx800m','-cp',SMALI_CP,'org.jf.baksmali.Main','d',str(out_path),'-o',str(check_dir)])
    ptxt = (check_dir/'litex'/'prm'/'PrmHandler.smali').read_text()
    stxt = (check_dir/'litex'/'bridge'/'Listener$Switch.smali').read_text()
    if 'const-string v0, "365"' not in ptxt or '0xd8cf' not in ptxt or 'Boolean;->TRUE' not in ptxt:
        raise RuntimeError('rebuilt PrmHandler missing verified Boolean/String contracts')
    if DIAG_GET_PRM and 'ProXGetPrm' not in ptxt:
        raise RuntimeError('diagnostic PrmHandler logging is missing')
    if stxt.count('disablePrivacySwitchSaving') != 3 or 'setSaveEnabled(Z)V' not in stxt:
        raise RuntimeError('rebuilt switch-state helper missing or call count wrong')
    if '.method public static native onCheckedCase22' not in stxt:
        raise RuntimeError('native onCheckedCase22 callback should remain intact for dialog tracing')
    wtxt_check = (check_dir/'litex'/'WaResources.smali').read_text()
    if 'SharedPreferences;->getBoolean' not in wtxt_check or '.method public static native getBoolean' in wtxt_check:
        raise RuntimeError('rebuilt WaResources.getBoolean is not the Java preference implementation')
    if DIAG_SET_BOOLEAN:
        if 'ProXSetBoolean' not in wtxt_check or '.method public static native setBoolean' in wtxt_check:
            raise RuntimeError('diagnostic setBoolean implementation is missing')
    elif '.method public static native setBoolean' not in wtxt_check:
        raise RuntimeError('native WaResources.setBoolean should be retained outside diagnostics')
    if TRACE_DIALOGS:
        if 'ProXDialogTrace' not in wtxt_check or '.method public static native getAlertDialog' in wtxt_check:
            raise RuntimeError('rebuilt WaResources.getAlertDialog diagnostic wrapper missing')
    elif '.method public static native getAlertDialog' not in wtxt_check:
        raise RuntimeError('native WaResources.getAlertDialog should be retained outside tracing builds')
    etxt_check = (check_dir/'litex'/'bridge'/'Extra.smali').read_text()
    if SUPPRESS_PRM_BANNER:
        if 'ProXSetPrmBanner' not in etxt_check or '.method public static native setPrmBanner' in etxt_check:
            raise RuntimeError('local setPrmBanner suppression wrapper missing')
    elif '.method public static native setPrmBanner' not in etxt_check:
        raise RuntimeError('native Extra.setPrmBanner should be retained outside local tests')
    return dict(source_sha256=sha(dex_path), patched_sha256=sha(out_path),
                bytes=out_path.stat().st_size, helper_calls=2, expiry_value='365 days (local test value)',
                premium_dialog_trace=('Java stack logging; native callback retained; diagnostic only'
                                     if TRACE_DIALOGS else 'native dialog helper retained'),
                premium_banner=('suppressed for local feature test; diagnostic only'
                                if SUPPRESS_PRM_BANNER else 'native banner retained'),
                set_boolean=('direct SharedPreferences writer with diagnostics'
                             if DIAG_SET_BOOLEAN else 'native writer retained'),
                get_prm_trace=DIAG_GET_PRM)


def patch_version(manifest, new_version):
    doc = Axml(manifest)
    found = False
    before = None
    raw = bytearray(doc.rest)
    for _, name, attrs in doc.elements():
        if name != 'manifest':
            continue
        for attr in attrs:
            off, ns, aname, raw_idx, dtype, ddata = attr
            if aname == 'versionCode':
                if dtype not in (0x10, 0x11):
                    raise RuntimeError(f'unexpected versionCode AXML type {dtype:#x}')
                before = ddata
                struct.pack_into('<I', raw, off+16, new_version)
                found = True
                break
    if not found:
        raise RuntimeError('manifest versionCode attribute not found')
    doc.rest = bytes(raw)
    return doc.to_bytes(), before


def repack(source, replacements, out):
    out.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source, out)
    stage = WORK/'stage'
    if stage.exists(): shutil.rmtree(stage)
    stage.mkdir(parents=True)
    for name, data in replacements.items():
        target=stage/name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    # Preserve exact APK paths, including native libraries under lib/arm64-v8a/.
    run(['zip','-q','-X',str(out)] + list(replacements), cwd=stage)
    with zipfile.ZipFile(out) as z:
        sigs=[n for n in z.namelist() if n.startswith('META-INF/') and n.upper().endswith(('.SF','.RSA','.DSA','.EC','MANIFEST.MF'))]
    if sigs:
        run(['zip','-q','-d',str(out)] + sigs)


def main():
    if not SRC.exists():
        raise SystemExit(f'missing exact linked base: {SRC}')
    WORK.mkdir(parents=True, exist_ok=True)
    started=time.time()
    base_sha=sha(SRC)
    with zipfile.ZipFile(SRC) as z:
        blobs={n:z.read(n) for n in ('classes6.dex','classes12.dex','classes14.dex','AndroidManifest.xml')}
        native_switch_report=[]
        if PATCH_PREMIUM_SWITCH_RESET:
            native_lib, native_switch_info = patch_premium_switch_reset(z.read('lib/arm64-v8a/liblitex.so'))
            blobs['lib/arm64-v8a/liblitex.so'] = native_lib
            native_switch_report.append(native_switch_info)
    ver_before=int(run(['aapt','dump','badging',str(SRC)]).split("versionCode='")[1].split("'")[0])
    if ver_before >= TARGET_VERSION:
        raise RuntimeError(f'base versionCode {ver_before} is not lower than target {TARGET_VERSION}')

    # Correct Samsung/other non-Pixel source path: code-unit offsets from the exact mf9mic DEX.
    d12, mic_reports = patch_many(blobs['classes12.dex'], [
        ('LX/Pyx;','A02',0x1ce,0x010a,0x0112,'ignore nonzero 0x34b3 override so S24U takes CAMCORDER fallback'),
    ])
    mic_reports.append(check_code_unit(d12,'LX/Pyx;','A02',0x1db,0x5812,
                                      'verified existing non-Pixel fallback is AudioSource.CAMCORDER'))

    # Anti View Once currently returns early at these two sites before the normal opened/read path.
    d6, receipt_reports = patch_many(blobs['classes6.dex'], [
        ('LX/AMs;','run',0xbf,0x000a,0x0012,'allow normal view-once opened/read path (click handler)'),
        ('LX/9sL;','A03',0x17,0x000a,0x0012,'allow normal view-once opened/read path (status handler)'),
    ])

    d14_in=WORK/'classes14.base.dex'; d14_in.write_bytes(blobs['classes14.dex'])
    d14_out=WORK/'classes14.dex'
    class14_report=patch_classes14(d14_in,d14_out)
    manifest, old_version=patch_version(blobs['AndroidManifest.xml'],TARGET_VERSION)
    if old_version != ver_before:
        raise RuntimeError(f'AXML versionCode {old_version} disagrees with aapt {ver_before}')

    replacements={'classes6.dex':d6,'classes12.dex':d12,'classes14.dex':d14_out.read_bytes(),'AndroidManifest.xml':manifest}
    if PATCH_PREMIUM_SWITCH_RESET:
        replacements['lib/arm64-v8a/liblitex.so'] = blobs['lib/arm64-v8a/liblitex.so']
    unsigned=WORK/'unsigned.apk'
    repack(SRC,replacements,unsigned)
    aligned=WORK/'aligned.apk'
    build_apk.zipalign(unsigned,aligned)
    verify=build_apk.sign(aligned)
    OUT.parent.mkdir(parents=True,exist_ok=True)
    aligned.replace(OUT)

    a=build_apk.entries(SRC); b=build_apk.entries(OUT)
    changed=sorted(k for k in a if k in b and a[k]!=b[k])
    allowed={'classes6.dex','classes12.dex','classes14.dex','AndroidManifest.xml',
             'META-INF/MANIFEST.MF','META-INF/PROX-MOD.RSA','META-INF/PROX-MOD.SF'}
    if PATCH_PREMIUM_SWITCH_RESET:
        allowed.add('lib/arm64-v8a/liblitex.so')
    extra=sorted(set(changed)-allowed)
    if extra: raise RuntimeError(f'unexpected APK entries changed: {extra}')
    bad=run(['zipalign','-c','-p','4',str(OUT)])
    badging=run(['aapt','dump','badging',str(OUT)])
    if f"versionCode='{TARGET_VERSION}'" not in badging:
        raise RuntimeError('target versionCode not reflected by aapt')
    if "versionName='2.26.42.74'" not in badging or "package: name='com.whatsapp.litex'" not in badging:
        raise RuntimeError('package/versionName changed unexpectedly')
    if 'CN=ProX Mod (a)' not in verify:
        raise RuntimeError('APK not signed with the same ProX identity')

    report={
        'source':str(SRC),'source_sha256':base_sha,'source_versionCode':ver_before,
        'output':str(OUT),'output_sha256':sha(OUT),'bytes':OUT.stat().st_size,
        'package':'com.whatsapp.litex','versionName':'2.26.42.74','versionCode':TARGET_VERSION,
        'signer':'CN=ProX Mod (a)','patches':{'mic':mic_reports,'view_once_receipt':receipt_reports,'classes14':class14_report,'native_calls_switch':native_switch_report},
        'changed_entries':changed,'unexpected_entries':extra,'zipalign_ok':True,
        'signature_verify':verify.strip().splitlines(),'seconds':round(time.time()-started,1)
    }
    REPORT.parent.mkdir(parents=True,exist_ok=True)
    REPORT.write_text(json.dumps(report,indent=2)+'\n')
    print(json.dumps(report,indent=2))

if __name__=='__main__':
    main()
