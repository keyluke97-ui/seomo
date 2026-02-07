"""
프로젝트 최종 점검 스크립트
GitHub 업로드 전에 모든 파일이 준비되었는지 확인
"""
import os
from pathlib import Path

# 현재 디렉토리
BASE_DIR = Path(__file__).parent

# 체크할 파일 목록
REQUIRED_FILES = {
    "Python Files": [
        "app.py",
        "scraper.py",
        "notion_bot.py",
        "config.py",
    ],
    "Config Files": [
        "requirements.txt",
        "packages.txt",
        ".gitignore",
    ],
    "Documentation": [
        "README.md",
        "DEPLOYMENT.md",
        "GITHUB_UPLOAD_GUIDE.md",
    ],
    "Example Files": [
        "user_config.json.example",
        ".streamlit/secrets.toml.example",
    ],
}

# 업로드하면 안 되는 파일
FORBIDDEN_FILES = [
    ".streamlit/secrets.toml",  # API Keys!
    "user_config.json",  # Personal settings
]


def check_file_exists(filepath):
    """파일이 존재하는지 확인"""
    full_path = BASE_DIR / filepath
    return full_path.exists()


def check_forbidden_files():
    """업로드하면 안 되는 파일 체크"""
    issues = []
    
    for forbidden in FORBIDDEN_FILES:
        if check_file_exists(forbidden):
            issues.append(f"WARNING: {forbidden} exists (DO NOT upload to GitHub!)")
    
    return issues


def main():
    print("=" * 60)
    print("GitHub Upload Check")
    print("=" * 60)
    print()
    
    all_ok = True
    
    # 1. 필수 파일 체크
    print("Required Files Check:")
    for category, files in REQUIRED_FILES.items():
        print(f"\n  [{category}]")
        for file in files:
            if check_file_exists(file):
                print(f"    [OK] {file}")
            else:
                print(f"    [MISSING] {file}")
                all_ok = False
    
    print("\n" + "-" * 60)
    
    # 2. 위험 파일 체크
    print("\nForbidden Files Check:")
    issues = check_forbidden_files()
    
    if issues:
        all_ok = False
        for issue in issues:
            print(f"  {issue}")
        print("\n  Note: .gitignore will exclude these automatically.")
    else:
        print("  [OK] No forbidden files found")
    
    print("\n" + "-" * 60)
    
    # 3. 파일 크기 체크
    print("\nProject Statistics:")
    total_size = 0
    file_count = 0
    
    for file_list in REQUIRED_FILES.values():
        for file in file_list:
            filepath = BASE_DIR / file
            if filepath.exists() and filepath.is_file():
                size = filepath.stat().st_size
                total_size += size
                file_count += 1
    
    print(f"  Files: {file_count}")
    print(f"  Total Size: {total_size / 1024:.2f} KB")
    
    print("\n" + "=" * 60)
    
    # 최종 결과
    if all_ok:
        print("\n[SUCCESS] All checks passed! Ready for GitHub upload")
        print("\nNext steps:")
        print("  1. Read GITHUB_UPLOAD_GUIDE.md")
        print("  2. Create GitHub repository")
        print("  3. Upload required files")
        print("  4. Deploy to Streamlit Cloud")
    else:
        print("\n[FAILED] Some issues found. Check messages above.")
    
    print("\n" + "=" * 60)


if __name__ == "__main__":
    main()
