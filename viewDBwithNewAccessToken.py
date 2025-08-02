
import dropbox

ACCESS_TOKEN = 'sl.u.AF7a1fVsFsVnb3wK17eK6LgAex2JHsFwLiYTVDO-QZPpRq40G1P-V59vGQGqASOlTfdDivBf--2HEt_wJFDBhrfwEPRt5NMqEgbvStbDb3lpyrRv7cmfF36g7OAbNNW2yA0BNUZ69VNFrJGiAjhmjcO8MuR-XVNZ92hKpV5I9tS_c-Zxx9yLTTWMxilqtjPUNVKHAkyYtSLXsWoqqZLvRyivGzcMXKWpt97P9TCsjIkjorE6nBl97ujkn32h7GVGCsZs_G9feEwv-tbkE_FP1yvtd2hnZIf-oTyl74_kAcf3-l_gcSTbgQh2DoBGCG50SJQHdlWRSopZm8Eh2c3jtArWPIhNwJoSHbF4SAm4OteKXzQSD_aZoBUHN54Zp4rPAumO_D9LqL48ZK6lSawEW_7IGV9xVoUiKc6O8CV7yUmtvezYBFSoRQwFOldfw-B3HkizPNMzrRkbpsnyFQS64RbVD1Q7BqvlddxOplrCTYJGGt5Y1oy0UWu_8w_tSbtyxE0WxrDzL55XzNlkk_6LKXTO3Mki2LUYo4ymmUdq5tZnnl_f0owiclIyFolHM4Hjc0lOEU57TAarDP6L8nqnoDZbWC2n1uEdDpu2Za2Vldr1-voMc9WHMA6LJBAbJ5RiYPpY1z62VBG0MepZjkX3-E57-AZD9ibL0sA299p67T3ij5ppKulgq7kBF_z0JwtVw78lYn-kV_aCP6wu7N6-nM0xhCKj3MhYUJ_jWMbo_PVLbMH96StDvPmBbdsqzIpI8IJkCakhOMJt1zG4dHncLnz7K9cXE6oGpMxv2026vAbiIFz1fBd03FRW9_uFfcWd5Zh89V6F7DPBwhs-oQtlhj2BLG0i_-YaGdNw1ngVa743l8VgDjU89Ct3CBQHQ7EYFM7-H9OgoXSg39CyqXaZevhnBLRX1H06bDCiqyOCqOjqOVUVIKJAqWfj7Ej3yjEMn9jbr4yjUji0he0NhmwFXvXi8dcZx9yCbYq8FUz5awrD9XZjTsoD3UldAxK9YB_18fqAm7b9Dh-ToL149i0dxFxVPwielEYK1Ke6tvgwKA62EfSBRIFuO34_JfBioiqpAZm3Hoj0xe_HpzvuDsBENiYxC1n6StLnoFDDLeVC2PifssxVweQuYOOr_1tTDkHknVaPkgCqQtfQJb7Hf5cK1gFAnnxPNRtMSMYMI4r5ad2gPFyfCB4ilzuBKl9aNp4LM_e_Fmmo-4-H5cSOEm4HigSDm0InCwrrRXwsKwtWu7-2pBfrwytQvFGXabaoyRIs_vJfSSHw4zY1Cax_iUrOkQMB'  # paste your long-lived access token


dbx = dropbox.Dropbox(ACCESS_TOKEN)

try:
    print("📁 Root folder contents:")
    result = dbx.files_list_folder(path="", recursive=False)

    for entry in result.entries:
        if isinstance(entry, dropbox.files.FolderMetadata):
            print(f"📂 {entry.name}")
        elif isinstance(entry, dropbox.files.FileMetadata):
            print(f"📄 {entry.name}")

    # Check if more entries exist (pagination)
    while result.has_more:
        result = dbx.files_list_folder_continue(result.cursor)
        for entry in result.entries:
            if isinstance(entry, dropbox.files.FolderMetadata):
                print(f"📂 {entry.name}")
            elif isinstance(entry, dropbox.files.FileMetadata):
                print(f"📄 {entry.name}")

except dropbox.exceptions.AuthError as e:
    print("❌ Auth failed:", e)
except dropbox.exceptions.ApiError as e:
    print("❌ API error:", e)

