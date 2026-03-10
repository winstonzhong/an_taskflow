#!/bin/bash

# =============================================================================
# an_taskflow 测试运行脚本
# 一键执行所有测试用例
# =============================================================================

# 颜色定义
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
NC='\033[0m' # No Color

# 脚本所在目录（项目根目录）
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# 打印带颜色的消息
print_info() {
    echo -e "${BLUE}[INFO]${NC} $1"
}

print_success() {
    echo -e "${GREEN}[SUCCESS]${NC} $1"
}

print_warning() {
    echo -e "${YELLOW}[WARNING]${NC} $1"
}

print_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

print_header() {
    echo -e "${CYAN}========================================${NC}"
    echo -e "${CYAN}$1${NC}"
    echo -e "${CYAN}========================================${NC}"
}

# 显示帮助信息
show_help() {
    cat << EOF
用法: ./run_tests.sh [选项]

选项:
    all         运行所有测试（排除慢测试）
    full        运行所有测试（包含慢测试，如信号处理）
    queue       只运行队列系统相关测试
    worker      只运行 Worker 相关测试
    signal      只运行信号处理测试（慢测试）
    skill       只运行技能配置测试
    failed      只运行上次失败的测试
    coverage    生成测试覆盖率报告
    list        列出所有可用的测试
    help        显示此帮助信息

示例:
    ./run_tests.sh              # 默认：运行所有测试（排除慢测试）
    ./run_tests.sh full         # 运行所有测试（包含慢测试）
    ./run_tests.sh skill        # 只运行技能配置测试
    ./run_tests.sh coverage     # 生成覆盖率报告

EOF
}

# 检查 pytest 是否安装
check_pytest() {
    if ! command -v pytest &> /dev/null; then
        print_error "未找到 pytest，请先安装测试依赖"
        print_info "安装命令: pip install pytest pytest-django"
        exit 1
    fi
}

# 运行测试的主函数
run_tests() {
    local extra_args="$1"
    local description="$2"
    
    print_header "$description"
    print_info "工作目录: $(pwd)"
    print_info "Python: $(python --version 2>&1)"
    print_info "Pytest: $(pytest --version 2>&1 | head -1)"
    echo ""
    
    # 执行测试
    pytest tests/ $extra_args
    local exit_code=$?
    
    echo ""
    if [ $exit_code -eq 0 ]; then
        print_success "测试通过！✅"
    else
        print_error "测试失败！❌ (退出码: $exit_code)"
    fi
    
    return $exit_code
}

# 主程序
main() {
    check_pytest
    
    local command="${1:-all}"
    
    case "$command" in
        help|-h|--help)
            show_help
            exit 0
            ;;
            
        all|"")
            # 默认：运行所有测试，排除慢测试
            run_tests "-v --tb=short -m 'not slow'" "运行所有测试（排除慢测试）"
            ;;
            
        full|--full)
            # 运行所有测试，包括慢测试
            print_warning "注意：信号处理测试会启动真实子进程，可能需要较长时间"
            run_tests "-v --tb=short" "运行所有测试（包含慢测试）"
            ;;
            
        queue)
            # 只运行队列相关测试
            run_tests "-v --tb=short -m queue" "队列系统测试"
            ;;
            
        worker)
            # 只运行 Worker 相关测试
            run_tests "-v --tb=short -m worker" "Worker 生命周期测试"
            ;;
            
        signal)
            # 只运行信号处理测试
            print_warning "注意：信号处理测试会启动真实子进程"
            run_tests "-v --tb=short -m signal" "信号处理测试"
            ;;
            
        skill|config)
            # 只运行技能配置测试
            run_tests "-v --tb=short tests/integration/test_skill_config.py" "技能配置测试"
            ;;
            
        integration)
            # 只运行所有集成测试
            run_tests "-v --tb=short tests/integration/" "所有集成测试"
            ;;
            
        failed|--failed|-f)
            # 只运行上次失败的测试
            run_tests "-v --tb=short --lf" "运行上次失败的测试"
            ;;
            
        coverage|--coverage|-c)
            # 生成覆盖率报告
            print_header "生成测试覆盖率报告"
            
            # 检查 coverage 是否安装
            if ! python -c "import pytest_cov" 2>/dev/null; then
                print_warning "未安装 pytest-cov，正在尝试安装..."
                pip install pytest-cov
            fi
            
            pytest tests/ -v --cov=. --cov-report=html --cov-report=term-missing -m 'not slow'
            local exit_code=$?
            
            echo ""
            if [ $exit_code -eq 0 ]; then
                print_success "测试通过！覆盖率报告已生成: htmlcov/index.html"
                print_info "可以用浏览器打开 htmlcov/index.html 查看详细报告"
            else
                print_error "测试失败！❌"
            fi
            exit $exit_code
            ;;
            
        list|--list|-l)
            # 列出所有可用的测试
            print_header "可用的测试列表"
            pytest tests/ --collect-only -q 2>/dev/null | grep "::" | head -50
            print_info "提示：使用 './run_tests.sh list -v' 查看完整列表"
            ;;
            
        *)
            print_error "未知的命令: $command"
            show_help
            exit 1
            ;;
    esac
}

# 运行主程序
main "$@"
