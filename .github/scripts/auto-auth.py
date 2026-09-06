#!/usr/bin/env python3
"""auto-auth 语义补丁：移除 Dopamine RH 的 supporter license 验证
- DOSupporterLicense.h: DORHSupporterVerifyLicenseCode 直接返回合法授权
- DOSettingsController.m: Supporter License 按钮点击直接自动激活
在仓库根目录运行: python3 scripts/auto-auth.py
"""
import pathlib
import re

ROOT = pathlib.Path(__file__).resolve().parent.parent.parent


def replace_function_body(src, signature, new_body, label):
    """按函数签名定位，用大括号配对替换整个函数体"""
    idx = src.find(signature)
    if idx == -1:
        raise SystemExit(f"ERROR: {label} signature not found:\n{signature}")
    brace_start = src.find('{', idx)
    if brace_start == -1:
        raise SystemExit(f"ERROR: {label} no function body found")
    depth = 0
    i = brace_start
    while i < len(src):
        if src[i] == '{':
            depth += 1
        elif src[i] == '}':
            depth -= 1
            if depth == 0:
                break
        i += 1
    return src[:idx] + new_body + src[i + 1:]


# ---------- 1) DOSupporterLicense.h ----------
h_path = ROOT / 'Application/Dopamine/UI/DOSupporterLicense.h'
src = h_path.read_text()

sig = 'static inline NSDictionary<NSString *, id> *DORHSupporterVerifyLicenseCode(NSString *licenseCode,\n                                                                           NSError **error)\n{'
body = '''static inline NSDictionary<NSString *, id> *DORHSupporterVerifyLicenseCode(NSString *licenseCode,
                                                                           NSError **error)
{
    // AUTO-PATCH: 移除签名验证，任何输入均视为有效授权
    NSString *currentDeviceCode = DORHSupporterDeviceCode();
    NSDictionary<NSString *, id> *autoInfo = @{
        @"v" : @1,
        @"product" : @"DopamineRH",
        @"sid" : @"auto-authorized",
        @"device" : currentDeviceCode.length > 0 ? currentDeviceCode : @"auto",
        @"ent" : @[ @"custom_glass" ],
    };
    return autoInfo;
}
'''
src = replace_function_body(src, sig, body, 'DOSupporterLicense.h VerifyLicenseCode')
h_path.write_text(src)
print('OK: DOSupporterLicense.h patched')

# ---------- 2) DOSettingsController.m ----------
m_path = ROOT / 'Application/Dopamine/UI/Settings/DOSettingsController.m'
src = m_path.read_text()

sig = '- (void)supporterLicensePressed\n{'
body = '''- (void)supporterLicensePressed
{
    // AUTO-PATCH: 点击按钮直接自动授权（无需输入激活码）
    NSDictionary<NSString *, id> *info = DORHSupporterCurrentLicenseInfo();
    NSString *supporterID = [info[@"sid"] isKindOfClass:NSString.class] ? info[@"sid"] : nil;
    NSString *deviceCode = DORHSupporterDeviceCode();

    __weak typeof(self) weakSelf = self;

    if (supporterID.length > 0) {
        // 已授权：显示状态 + 移除选项
        NSString *message = [NSString stringWithFormat:@"Verified\\n\\nDevice Code\\n%@",
                             deviceCode.length > 0 ? deviceCode : @"Unavailable"];
        UIAlertController *alert = [UIAlertController alertControllerWithTitle:@"Supporter License"
                                                                       message:message
                                                                preferredStyle:UIAlertControllerStyleAlert];
        [alert addAction:[UIAlertAction actionWithTitle:@"Copy Device Code"
                                                  style:UIAlertActionStyleDefault
                                                handler:^(__kindof UIAlertAction * _Nonnull action) {
            UIPasteboard.generalPasteboard.string = deviceCode;
        }]];
        [alert addAction:[UIAlertAction actionWithTitle:@"Remove License"
                                                  style:UIAlertActionStyleDestructive
                                                handler:^(__kindof UIAlertAction * _Nonnull action) {
            DORHSupporterRemoveLicense();
            [weakSelf showSupporterLicenseChangeWithTitle:@"Supporter Removed"
                                                  message:@"Your supporter license has been removed. Restore the standard interface now."];
        }]];
        [alert addAction:[UIAlertAction actionWithTitle:@"Cancel" style:UIAlertActionStyleCancel handler:nil]];
        [self presentViewController:alert animated:YES completion:nil];
        return;
    }

    // 未授权：直接自动激活
    NSError *error = nil;
    if (DORHSupporterStoreLicenseCode(@"RH1.auto.auto", &error)) {
        [self showSupporterLicenseChangeWithTitle:@"Supporter Activated"
                                          message:@"Your supporter license has been saved. Apply the Supporter interface now."];
    }
    else {
        [self showSupporterLicenseResultWithTitle:@"Activation Failed"
                                          message:error.localizedDescription ?: @"Unable to verify supporter license"];
    }
}
'''
src = replace_function_body(src, sig, body, 'DOSettingsController.m supporterLicensePressed')
m_path.write_text(src)
print('OK: DOSettingsController.m patched')
