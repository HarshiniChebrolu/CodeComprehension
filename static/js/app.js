/**
 * CodeComprehension — Core Interactive Application Logic
 * Pair Programming & AI Coding Mentor System
 */

document.addEventListener("DOMContentLoaded", () => {
    // State Store
    const state = {
        language: "python",
        code: "",
        reviewData: null,
        issues: [],
        currentHints: {},     // bug_id -> current level (1, 2, 3)
        visualizer: {
            frames: [],
            totalSteps: 0,
            currentStep: 0,
            isPlaying: false,
            timer: null,
            speedMs: 600
        }
    };

    // DOM Elements
    const codeEditor = document.getElementById("codeEditor");
    const lineNumbers = document.getElementById("lineNumbers");
    const highlightCode = document.getElementById("highlightCode");
    const highlightSurface = document.getElementById("highlightSurface");
    const cursorPos = document.getElementById("cursorPos");
    const languageSelect = document.getElementById("languageSelect");
    const samplePreset = document.getElementById("samplePreset");
    const reviewBtn = document.getElementById("reviewBtn");
    const reviewSpinner = document.getElementById("reviewSpinner");
    const reviewBtnText = document.getElementById("reviewBtnText");
    const runCodeBtn = document.getElementById("runCodeBtn");
    const formatBtn = document.getElementById("formatBtn");
    const copyBtn = document.getElementById("copyBtn");
    const clearBtn = document.getElementById("clearBtn");
    const editorStatusPill = document.getElementById("editorStatusPill");
    const activeFileName = document.getElementById("activeFileName");

    // Console Elements
    const stdoutText = document.getElementById("stdoutText");
    const stderrText = document.getElementById("stderrText");
    const stdinInput = document.getElementById("stdinInput");
    const execDuration = document.getElementById("execDuration");
    const consoleStatusBadge = document.getElementById("consoleStatusBadge");
    const clearConsoleBtn = document.getElementById("clearConsoleBtn");

    // Hub Navigation
    const hubTabs = document.querySelectorAll(".hub-tab");
    const hubPanels = document.querySelectorAll(".hub-panel");
    const issueCountPill = document.getElementById("issueCountPill");
    const scoreSummaryPill = document.getElementById("scoreSummaryPill");

    // Mentor & Review
    const issuesListContainer = document.getElementById("issuesListContainer");
    const summaryStatusTitle = document.getElementById("summaryStatusTitle");
    const summaryStatusDesc = document.getElementById("summaryStatusDesc");

    // Quality Score
    const scoreNumberVal = document.getElementById("scoreNumberVal");
    const scoreRingCircle = document.getElementById("scoreRingCircle");
    const scoreVerdict = document.getElementById("scoreVerdict");

    // Explanation
    const explPurpose = document.getElementById("explPurpose");
    const explAlgorithm = document.getElementById("explAlgorithm");
    const explDataStructures = document.getElementById("explDataStructures");
    const explStepList = document.getElementById("explStepList");
    const explMentorNote = document.getElementById("explMentorNote");
    const explProviderBadge = document.getElementById("explProviderBadge");

    // AST Insight
    const astFuncCount = document.getElementById("astFuncCount");
    const astLoopCount = document.getElementById("astLoopCount");
    const astBranchCount = document.getElementById("astBranchCount");
    const astDepthCount = document.getElementById("astDepthCount");
    const astFlowPipeline = document.getElementById("astFlowPipeline");
    const astNodesList = document.getElementById("astNodesList");

    // Complexity
    const compTimeVal = document.getElementById("compTimeVal");
    const compTimeReason = document.getElementById("compTimeReason");
    const compSpaceVal = document.getElementById("compSpaceVal");
    const compSpaceReason = document.getElementById("compSpaceReason");
    const scenBestBound = document.getElementById("scenBestBound");
    const scenBestDesc = document.getElementById("scenBestDesc");
    const scenAvgBound = document.getElementById("scenAvgBound");
    const scenAvgDesc = document.getElementById("scenAvgDesc");
    const scenWorstBound = document.getElementById("scenWorstBound");
    const scenWorstDesc = document.getElementById("scenWorstDesc");
    const compHotspotsList = document.getElementById("compHotspotsList");

    // Test Cases
    const testCardsContainer = document.getElementById("testCardsContainer");
    const tcTotalCount = document.getElementById("tcTotalCount");
    const tcPassedCount = document.getElementById("tcPassedCount");
    const tcFailedCount = document.getElementById("tcFailedCount");
    const runAllTestsBtn = document.getElementById("runAllTestsBtn");

    // Optimization
    const optCurrentComp = document.getElementById("optCurrentComp");
    const optTargetComp = document.getElementById("optTargetComp");
    const optTitle = document.getElementById("optTitle");
    const optSummary = document.getElementById("optSummary");
    const optWhatChanges = document.getElementById("optWhatChanges");
    const optWhyImproves = document.getElementById("optWhyImproves");
    const optTradeOffs = document.getElementById("optTradeOffs");
    const optWhenUseful = document.getElementById("optWhenUseful");
    const toggleOptimizedCodeBtn = document.getElementById("toggleOptimizedCodeBtn");
    const optimizedCodeWrapper = document.getElementById("optimizedCodeWrapper");
    const optimizedDiffPre = document.getElementById("optimizedDiffPre");
    const applyOptimizedBtn = document.getElementById("applyOptimizedBtn");

    // Visualizer Controls
    const visStage = document.getElementById("visStage");
    const visAlgoTitle = document.getElementById("visAlgoTitle");
    const visAlgoSub = document.getElementById("visAlgoSub");
    const visCurrentStep = document.getElementById("visCurrentStep");
    const visTotalSteps = document.getElementById("visTotalSteps");
    const visStepMessage = document.getElementById("visStepMessage");
    const visCodeLine = document.getElementById("visCodeLine");
    const visPlayPauseBtn = document.getElementById("visPlayPauseBtn");
    const playIcon = document.getElementById("playIcon");
    const pauseIcon = document.getElementById("pauseIcon");
    const visStepBackBtn = document.getElementById("visStepBackBtn");
    const visStepForwardBtn = document.getElementById("visStepForwardBtn");
    const visRestartBtn = document.getElementById("visRestartBtn");
    const visSpeedSelect = document.getElementById("visSpeedSelect");

    // History & Modals
    const historyToggleBtn = document.getElementById("historyToggleBtn");
    const historyDrawer = document.getElementById("historyDrawer");
    const closeHistoryBtn = document.getElementById("closeHistoryBtn");
    const historyList = document.getElementById("historyList");
    const solutionModal = document.getElementById("solutionModal");
    const closeModalBtn = document.getElementById("closeModalBtn");
    const modalProblemTitle = document.getElementById("modalProblemTitle");
    const modalSolutionCode = document.getElementById("modalSolutionCode");
    const modalWhyFailed = document.getElementById("modalWhyFailed");
    const modalWhyWorks = document.getElementById("modalWhyWorks");
    const copySolutionBtn = document.getElementById("copySolutionBtn");
    const insertSolutionBtn = document.getElementById("insertSolutionBtn");

    // Sample Snippets across multiple languages
    const PRESETS = {
        find_max_bug: {
            lang: "python",
            file: "find_max.py",
            code: `def find_maximum(numbers):
    # Educational Bug: Initializing max tracker to 0
    # Notice what happens when the input list contains only negative numbers!
    max_val = 0
    
    for num in numbers:
        if num > max_val:
            max_val = num
            
    return max_val
`
        },
        two_sum_bug: {
            lang: "python",
            file: "two_sum.py",
            code: `def two_sum(nums, target):
    # Bug 1: Allows identical index i == j to pair with itself (e.g. nums=[3,2,4], target=6 -> returns [0, 0] incorrectly)
    # Bug 2: O(n²) nested brute-force search when O(n) is possible
    for i in range(len(nums)):
        for j in range(len(nums)):
            if nums[i] + nums[j] == target:
                return [i, j]
                
    return []
`
        },
        bubble_sort_vis: {
            lang: "python",
            file: "bubble_sort.py",
            code: `def bubble_sort(arr):
    # Classic comparison sorting algorithm
    # Generates step-by-step array comparisons and swaps in the Visualizer!
    n = len(arr)
    for i in range(n):
        for j in range(0, n - i - 1):
            if arr[j] > arr[j + 1]:
                arr[j], arr[j + 1] = arr[j + 1], arr[j]
    return arr
`
        },
        binary_search_bug: {
            lang: "python",
            file: "binary_search.py",
            code: `def binary_search(arr, target):
    # Educational Bug: Off-by-one condition high = len(arr) and while low < high
    # Misses checking the last element when target is at arr[len(arr)-1]
    low = 0
    high = len(arr)
    
    while low < high:
        mid = (low + high) // 2
        if arr[mid] == target:
            return mid
        elif arr[mid] < target:
            low = mid + 1
        else:
            high = mid - 1
            
    return -1
`
        },
        unsafe_dict_access: {
            lang: "python",
            file: "user_service.py",
            code: `def format_user_profile(user_dict):
    # Runtime Risk: Direct bracket access raises KeyError if key is missing from payload
    # Best practice is to use .get() with fallback or guard with 'in'
    name = user_dict["name"]
    email = user_dict["email"]
    role = user_dict["role"]
    
    return f"{name} ({role}): {email}"
`
        },
        fib_recursion: {
            lang: "python",
            file: "fibonacci.py",
            code: `def fibonacci(n):
    # Inefficient O(2ⁿ) branching recursion with massive overlapping subproblems
    # Check the Optimization and Complexity tabs!
    if n <= 0:
        return 0
    if n == 1:
        return 1
    return fibonacci(n - 1) + fibonacci(n - 2)
`
        },
        cpp_two_sum_bug: {
            lang: "cpp",
            file: "two_sum.cpp",
            code: `#include <iostream>
#include <vector>
using namespace std;

vector<int> twoSum(vector<int>& nums, int target) {
    // Bug: Allows identical index i == j to pair with itself!
    // Nested brute force O(n²) comparison
    for (int i = 0; i < nums.size(); i++) {
        for (int j = 0; j < nums.size(); j++) {
            if (nums[i] + nums[j] == target) {
                return {i, j};
            }
        }
    }
    return {};
}

int main() {
    vector<int> nums = {3, 2, 4};
    int target = 6;
    vector<int> result = twoSum(nums, target);
    if (!result.empty()) {
        cout << "Indices: " << result[0] << ", " << result[1] << endl;
    }
    return 0;
}
`
        },
        cpp_preprocessor_bug: {
            lang: "cpp",
            file: "main.cpp",
            code: `#include <iostream>
#include <vector>
using namespace std;

// In C++, preprocessor directives start with #
// Notice how cleanly CodeComprehension highlights and parses this without HTML escaping errors!
int main() {
    cout << "Welcome to CodeComprehension C++ Reviewer!" << endl;
    vector<int> data = {10, 20, 30};
    for (int i = 0; i < data.size(); i++) {
        cout << "Item: " << data[i] << endl;
    }
    return 0;
}
`
        },
        cpp_bubble_sort: {
            lang: "cpp",
            file: "bubble_sort.cpp",
            code: `#include <iostream>
#include <vector>
using namespace std;

void bubbleSort(vector<int>& arr) {
    int n = arr.size();
    for (int i = 0; i < n; i++) {
        for (int j = 0; j < n - i - 1; j++) {
            if (arr[j] > arr[j + 1]) {
                swap(arr[j], arr[j + 1]);
            }
        }
    }
}

int main() {
    vector<int> arr = {64, 34, 25, 12, 22, 11, 90};
    bubbleSort(arr);
    cout << "Sorted array successfully!" << endl;
    return 0;
}
`
        },
        c_reverse_array: {
            lang: "c",
            file: "reverse.c",
            code: `#include <stdio.h>

void reverseArray(int arr[], int size) {
    int start = 0;
    int end = size - 1;
    while (start < end) {
        int temp = arr[start];
        arr[start] = arr[end];
        arr[end] = temp;
        start++;
        end--;
    }
}

int main() {
    int data[] = {1, 2, 3, 4, 5};
    reverseArray(data, 5);
    printf("First reversed element: %d\\n", data[0]);
    return 0;
}
`
        },
        java_string_equals: {
            lang: "java",
            file: "UserAuth.java",
            code: `public class UserAuth {
    public static boolean verifyToken(String providedRole) {
        // Educational Bug: Using '==' for String comparison instead of .equals()
        // In Java, '==' tests object memory identity, not string content!
        if (providedRole == "ADMIN") {
            return true;
        }
        return false;
    }

    public static void main(String[] args) {
        String role = new String("ADMIN");
        boolean auth = verifyToken(role);
        System.out.println("Authorized: " + auth);
    }
}
`
        },
        java_find_max: {
            lang: "java",
            file: "MaxFinder.java",
            code: `public class MaxFinder {
    public static int findMax(int[] numbers) {
        // Bug: max tracker initialized to 0 fails for negative arrays
        int maxVal = 0;
        for (int i = 0; i < numbers.length; i++) {
            if (numbers[i] > maxVal) {
                maxVal = numbers[i];
            }
        }
        return maxVal;
    }

    public static void main(String[] args) {
        int[] arr = {-10, -5, -20, -1};
        System.out.println("Max: " + findMax(arr));
    }
}
`
        },
        js_two_sum: {
            lang: "javascript",
            file: "twoSum.js",
            code: `function twoSum(nums, target) {
    // Two Sum in JavaScript using Map
    const seen = new Map();
    for (let i = 0; i < nums.length; i++) {
        const complement = target - nums[i];
        if (seen.has(complement)) {
            return [seen.get(complement), i];
        }
        seen.set(nums[i], i);
    }
    return [];
}

const nums = [2, 7, 11, 15];
const target = 9;
console.log("Indices:", twoSum(nums, target));
`
        }
    };

    // Initialize Editor with Default Preset
    loadPreset("find_max_bug");

    // ==========================================================================
    // Editor Helpers & Single-Pass Language-Aware Tokenizer
    // ==========================================================================

    function updateLineNumbers(code) {
        const lines = code.split("\n");
        const count = Math.max(1, lines.length);

        const issueLines = new Set();
        if (state.issues) {
            state.issues.forEach(i => {
                if (i.line) issueLines.add(i.line);
            });
        }

        let html = "";
        for (let i = 1; i <= count; i++) {
            const hasIssue = issueLines.has(i);
            html += `<span class="line-num-item ${hasIssue ? 'has-issue' : ''}" title="${hasIssue ? 'Finding on line ' + i : ''}">${i}</span>\n`;
        }
        lineNumbers.innerHTML = html;
    }

    function updateSyntaxHighlight(code, lang) {
        if (!code) {
            highlightCode.innerHTML = "\n";
            return;
        }
        const currentLang = (lang || state.language || "python").toLowerCase();
        highlightCode.innerHTML = tokenizeAndHighlight(code, currentLang) + "\n";
    }

    /**
     * Single-pass lexer and tokenizer that eliminates HTML attribute corruption bugs.
     * Accurately recognizes preprocessors (#include), comments, keywords, and strings per language.
     */
    function tokenizeAndHighlight(code, lang) {
        let tokenRegex;
        if (lang === "c" || lang === "cpp") {
            // Group 1: Preprocessor directive (#include <iostream>, #define, #incluude...)
            // Group 2: Comments (// or /* ... */)
            // Group 3: Strings ("..." or '...')
            // Group 4: Keywords & Types
            // Group 5: Numbers
            tokenRegex = /(#[a-zA-Z_]\w*(?:\s*<[^>\n]+>|\s*"[^"\n]+"|[^\n]*)?)|(\/\/[^\n]*|\/\*[\s\S]*?\*\/)|("(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*')|(\b(?:int|float|double|char|void|bool|auto|const|static|struct|class|public|private|protected|virtual|template|typename|namespace|using|std|cout|cin|endl|return|if|else|for|while|do|switch|case|break|continue|new|delete|sizeof|vector|string|map|set|include|main|unsigned|long|short|nullptr|true|false)\b)|(\b\d+(?:\.\d+)?\b)/g;
        } else if (lang === "java") {
            tokenRegex = /(\/\/[^\n]*|\/\*[\s\S]*?\*\/)|("(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*')|(\b(?:public|private|protected|static|final|class|interface|extends|implements|void|int|double|float|char|boolean|byte|short|long|return|if|else|for|while|do|switch|case|break|continue|new|this|super|try|catch|finally|throw|throws|package|import|null|true|false|String|System|out|println|Scanner|List|ArrayList|Map|HashMap)\b)|(\b\d+(?:\.\d+)?\b)/g;
        } else if (lang === "javascript" || lang === "js") {
            tokenRegex = /(\/\/[^\n]*|\/\*[\s\S]*?\*\/)|("(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*'|`(?:\\[\s\S]|[^\\`])*`)|(\b(?:const|let|var|function|return|if|else|for|while|do|switch|case|break|continue|new|this|class|extends|import|export|default|from|try|catch|finally|throw|async|await|yield|null|undefined|true|false|console|log|typeof|instanceof)\b)|(\b\d+(?:\.\d+)?\b)/g;
        } else {
            // Python
            // Group 1: Comment (#...)
            // Group 2: Strings (triple or single quotes)
            // Group 3: Decorators (@...)
            // Group 4: Keywords
            // Group 5: Built-ins
            // Group 6: Numbers
            tokenRegex = /(#[^\n]*)|("""[\s\S]*?"""|'''[\s\S]*?'''|"(?:\\.|[^"\\])*"|'(?:\\.|[^'\\])*')|(@[a-zA-Z_]\w*)|(\b(?:def|class|return|if|elif|else|for|while|in|is|not|and|or|try|except|finally|raise|import|from|as|with|pass|break|continue|None|True|False|lambda|yield|global|nonlocal|async|await)\b)|(\b(?:print|len|range|int|str|float|list|dict|set|tuple|sum|max|min|enumerate|zip|map|filter|sorted|open|type|id)\b)|(\b\d+(?:\.\d+)?\b)/g;
        }

        let lastIndex = 0;
        let result = "";
        let match;

        while ((match = tokenRegex.exec(code)) !== null) {
            if (match.index > lastIndex) {
                result += escapeHtml(code.substring(lastIndex, match.index));
            }

            const fullMatch = match[0];
            let tokenClass = "tok-plain";

            if (lang === "c" || lang === "cpp") {
                if (match[1]) tokenClass = "tok-preprocessor";
                else if (match[2]) tokenClass = "tok-comment";
                else if (match[3]) tokenClass = "tok-string";
                else if (match[4]) tokenClass = "tok-keyword";
                else if (match[5]) tokenClass = "tok-number";
            } else if (lang === "java") {
                if (match[1]) tokenClass = "tok-comment";
                else if (match[2]) tokenClass = "tok-string";
                else if (match[3]) tokenClass = "tok-keyword";
                else if (match[4]) tokenClass = "tok-number";
            } else if (lang === "javascript" || lang === "js") {
                if (match[1]) tokenClass = "tok-comment";
                else if (match[2]) tokenClass = "tok-string";
                else if (match[3]) tokenClass = "tok-keyword";
                else if (match[4]) tokenClass = "tok-number";
            } else {
                // Python
                if (match[1]) tokenClass = "tok-comment";
                else if (match[2]) tokenClass = "tok-string";
                else if (match[3]) tokenClass = "tok-def";
                else if (match[4]) tokenClass = "tok-keyword";
                else if (match[5]) tokenClass = "tok-builtin";
                else if (match[6]) tokenClass = "tok-number";
            }

            result += `<span class="${tokenClass}">${escapeHtml(fullMatch)}</span>`;
            lastIndex = tokenRegex.lastIndex;
        }

        if (lastIndex < code.length) {
            result += escapeHtml(code.substring(lastIndex));
        }

        return result;
    }

    function syncEditorScroll() {
        lineNumbers.scrollTop = codeEditor.scrollTop;
        highlightSurface.scrollTop = codeEditor.scrollTop;
        highlightSurface.scrollLeft = codeEditor.scrollLeft;
    }

    function updateCursorPosition() {
        const text = codeEditor.value.substr(0, codeEditor.selectionStart);
        const lines = text.split("\n");
        const line = lines.length;
        const col = lines[lines.length - 1].length + 1;
        cursorPos.textContent = `Ln ${line}, Col ${col}`;
    }

    let editorInputDebounce = null;
    codeEditor.addEventListener("input", () => {
        state.code = codeEditor.value;
        editorStatusPill.textContent = "Modified";
        editorStatusPill.className = "status-pill status-ready";
        
        clearTimeout(editorInputDebounce);
        editorInputDebounce = setTimeout(() => {
            updateLineNumbers(state.code);
            updateSyntaxHighlight(state.code, state.language);
        }, 50);
    });

    codeEditor.addEventListener("scroll", syncEditorScroll);
    codeEditor.addEventListener("keyup", updateCursorPosition);
    codeEditor.addEventListener("click", updateCursorPosition);

    // Professional VS Code-grade Editor Ergonomics: Auto-closing pairs, wrapping, indent
    const AUTO_PAIRS = {
        '(': ')',
        '[': ']',
        '{': '}',
        '"': '"',
        "'": "'",
        '`': '`'
    };
    const CLOSING_CHARS = new Set([')', ']', '}', '"', "'", '`']);

    codeEditor.addEventListener("keydown", (e) => {
        const start = codeEditor.selectionStart;
        const end = codeEditor.selectionEnd;
        const value = codeEditor.value;

        // 1. Tab & Shift+Tab Indentation
        if (e.key === "Tab") {
            e.preventDefault();
            if (e.shiftKey) {
                // Shift+Tab: Unindent
                if (start === end) {
                    const lineStart = value.lastIndexOf("\n", start - 1) + 1;
                    const beforeCursor = value.substring(lineStart, start);
                    const spacesToRemove = Math.min(4, beforeCursor.length - beforeCursor.replace(/ {1,4}$/, '').length);
                    if (spacesToRemove > 0) {
                        codeEditor.value = value.substring(0, start - spacesToRemove) + value.substring(start);
                        codeEditor.selectionStart = codeEditor.selectionEnd = start - spacesToRemove;
                        codeEditor.dispatchEvent(new Event("input"));
                    }
                } else {
                    const lineStart = value.lastIndexOf("\n", start - 1) + 1;
                    const lineEnd = value.indexOf("\n", end);
                    const finalEnd = lineEnd === -1 ? value.length : lineEnd;
                    const selectedBlock = value.substring(lineStart, finalEnd);
                    const unindented = selectedBlock.split("\n").map(l => l.replace(/^ {1,4}/, "")).join("\n");
                    codeEditor.value = value.substring(0, lineStart) + unindented + value.substring(finalEnd);
                    codeEditor.selectionStart = lineStart;
                    codeEditor.selectionEnd = lineStart + unindented.length;
                    codeEditor.dispatchEvent(new Event("input"));
                }
            } else {
                // Regular Tab: Indent
                if (start === end) {
                    codeEditor.value = value.substring(0, start) + "    " + value.substring(end);
                    codeEditor.selectionStart = codeEditor.selectionEnd = start + 4;
                    codeEditor.dispatchEvent(new Event("input"));
                } else {
                    const lineStart = value.lastIndexOf("\n", start - 1) + 1;
                    const lineEnd = value.indexOf("\n", end);
                    const finalEnd = lineEnd === -1 ? value.length : lineEnd;
                    const selectedBlock = value.substring(lineStart, finalEnd);
                    const indented = selectedBlock.split("\n").map(l => "    " + l).join("\n");
                    codeEditor.value = value.substring(0, lineStart) + indented + value.substring(finalEnd);
                    codeEditor.selectionStart = lineStart;
                    codeEditor.selectionEnd = lineStart + indented.length;
                    codeEditor.dispatchEvent(new Event("input"));
                }
            }
            return;
        }

        // 2. Auto-closing pairs and Selection Wrapping
        if (AUTO_PAIRS[e.key]) {
            const openChar = e.key;
            const closeChar = AUTO_PAIRS[openChar];

            // If text is selected, wrap the selection!
            if (start !== end) {
                e.preventDefault();
                const selectedText = value.substring(start, end);
                const wrapped = openChar + selectedText + closeChar;
                codeEditor.value = value.substring(0, start) + wrapped + value.substring(end);
                codeEditor.selectionStart = start + 1;
                codeEditor.selectionEnd = end + 1;
                codeEditor.dispatchEvent(new Event("input"));
                return;
            }

            // If quote and next character is identical quote, skip/step over
            if ((openChar === '"' || openChar === "'" || openChar === '`') && value[start] === openChar) {
                e.preventDefault();
                codeEditor.selectionStart = codeEditor.selectionEnd = start + 1;
                updateCursorPosition();
                return;
            }

            // Normal insertion of pair
            e.preventDefault();
            codeEditor.value = value.substring(0, start) + openChar + closeChar + value.substring(end);
            codeEditor.selectionStart = codeEditor.selectionEnd = start + 1;
            codeEditor.dispatchEvent(new Event("input"));
            return;
        }

        // 3. Skip closing character if next character matches
        if (CLOSING_CHARS.has(e.key) && value[start] === e.key) {
            e.preventDefault();
            codeEditor.selectionStart = codeEditor.selectionEnd = start + 1;
            updateCursorPosition();
            return;
        }

        // 4. Smart Backspace: Delete matching empty pair
        if (e.key === "Backspace" && start === end && start > 0) {
            const prevChar = value[start - 1];
            const nextChar = value[start];
            if (AUTO_PAIRS[prevChar] === nextChar) {
                e.preventDefault();
                codeEditor.value = value.substring(0, start - 1) + value.substring(start + 1);
                codeEditor.selectionStart = codeEditor.selectionEnd = start - 1;
                codeEditor.dispatchEvent(new Event("input"));
                return;
            }
        }

        // 5. Smart Enter: Auto-indentation and newline expansion between { and }
        if (e.key === "Enter" && start === end) {
            const prevChar = value[start - 1];
            const nextChar = value[start];
            const lineStart = value.lastIndexOf("\n", start - 1) + 1;
            const currentLine = value.substring(lineStart, start);
            const indentMatch = currentLine.match(/^\s*/);
            const currentIndent = indentMatch ? indentMatch[0] : "";

            if (prevChar === "{" && nextChar === "}") {
                e.preventDefault();
                const innerIndent = currentIndent + "    ";
                const insertText = "\n" + innerIndent + "\n" + currentIndent;
                codeEditor.value = value.substring(0, start) + insertText + value.substring(end);
                codeEditor.selectionStart = codeEditor.selectionEnd = start + innerIndent.length + 1;
                codeEditor.dispatchEvent(new Event("input"));
                return;
            } else if (currentIndent || currentLine.trim().endsWith("{") || currentLine.trim().endsWith(":")) {
                e.preventDefault();
                let extraIndent = "";
                if (currentLine.trim().endsWith("{") || currentLine.trim().endsWith(":")) {
                    extraIndent = "    ";
                }
                const insertText = "\n" + currentIndent + extraIndent;
                codeEditor.value = value.substring(0, start) + insertText + value.substring(end);
                codeEditor.selectionStart = codeEditor.selectionEnd = start + insertText.length;
                codeEditor.dispatchEvent(new Event("input"));
                return;
            }
        }
    });

    // Preset & Language Changing
    samplePreset.addEventListener("change", (e) => {
        loadPreset(e.target.value);
    });

    function loadPreset(key) {
        const preset = PRESETS[key];
        if (!preset) return;
        codeEditor.value = preset.code;
        state.code = preset.code;
        state.language = preset.lang;
        languageSelect.value = preset.lang;
        activeFileName.textContent = preset.file;
        updateLineNumbers(state.code);
        updateSyntaxHighlight(state.code, state.language);
        updateCursorPosition();
        setTimeout(performReview, 50);
    }

    async function loadLanguages() {
        try {
            const resp = await fetch("/api/v1/languages");
            if (!resp.ok) return;
            const data = await resp.json();
            if (data.success && data.languages && languageSelect) {
                const currentVal = languageSelect.value || state.language || "python";
                languageSelect.innerHTML = "";
                const list = Array.isArray(data.languages) ? data.languages : Object.entries(data.languages).map(([k, v]) => ({ language: k, ...v }));
                list.forEach((item) => {
                    const langKey = item.language;
                    if (!langKey) return;
                    const opt = document.createElement("option");
                    opt.value = langKey;
                    const readyIndicator = item.runnable ? "✓ Ready" : "Static";
                    const displayName = item.display_name || langKey.toUpperCase();
                    opt.textContent = `${displayName} (${readyIndicator})`;
                    if (langKey === currentVal) opt.selected = true;
                    languageSelect.appendChild(opt);
                });
            }
        } catch (e) {
            console.warn("Could not fetch dynamic language registry:", e);
        }
    }
    loadLanguages();

    languageSelect.addEventListener("change", (e) => {
        pauseVisualization();
        state.language = e.target.value;
        const exts = { python: ".py", c: ".c", cpp: ".cpp", java: ".java", javascript: ".js" };
        activeFileName.textContent = (state.language === "java" ? "Main" : "main") + (exts[state.language] || ".txt");

        // Automatically switch to first matching preset for this language
        const langPresetMap = {
            python: "find_max_bug",
            cpp: "cpp_two_sum_bug",
            c: "c_reverse_array",
            java: "java_string_equals",
            javascript: "js_two_sum"
        };
        const targetPreset = langPresetMap[state.language];
        if (targetPreset && PRESETS[targetPreset]) {
            samplePreset.value = targetPreset;
            loadPreset(targetPreset);
        } else {
            updateSyntaxHighlight(codeEditor.value, state.language);
        }
    });

    // Format Button
    formatBtn.addEventListener("click", () => {
        const cleaned = codeEditor.value
            .split("\n")
            .map(line => line.replace(/\s+$/, ""))
            .join("\n");
        codeEditor.value = cleaned;
        state.code = cleaned;
        updateSyntaxHighlight(cleaned);
        flashButton(formatBtn, "Formatted!");
    });

    // Copy Button
    copyBtn.addEventListener("click", () => {
        navigator.clipboard.writeText(codeEditor.value);
        flashButton(copyBtn, "Copied!");
    });

    // Clear Button
    clearBtn.addEventListener("click", () => {
        if (confirm("Clear editor contents?")) {
            codeEditor.value = "";
            state.code = "";
            updateLineNumbers("");
            updateSyntaxHighlight("");
            clearReviewResults();
        }
    });

    function flashButton(btn, text) {
        const orig = btn.innerHTML;
        btn.textContent = text;
        setTimeout(() => { btn.innerHTML = orig; }, 1200);
    }

    // ==========================================================================
    // Hub Tabs Navigation
    // ==========================================================================

    hubTabs.forEach(tab => {
        tab.addEventListener("click", () => {
            const target = tab.dataset.tab;
            hubTabs.forEach(t => t.classList.remove("active"));
            hubPanels.forEach(p => p.classList.remove("active"));

            tab.classList.add("active");
            const panel = document.getElementById(`panel-${target}`);
            if (panel) panel.classList.add("active");

            if (target === "threed") {
                if (state.reviewData && state.reviewData.topology_3d) {
                    if (!threeDState.scene || !threeDState.nodeMeshes.length) {
                        init3DTopology(state.reviewData.topology_3d);
                    }
                }
                setTimeout(window.resize3D, 30);
                setTimeout(window.resize3D, 180);
            } else if (target === "visualizer") {
                if (state.visualizer.frames && state.visualizer.frames.length) {
                    renderCurrentFrame();
                }
            }
        });
    });

    // ==========================================================================
    // Review Code — Core Pipeline Trigger
    // ==========================================================================

    reviewBtn.addEventListener("click", performReview);

    let currentReviewAbortController = null;

    async function performReview() {
        const code = codeEditor.value;
        if (!code.trim()) {
            alert("Please enter code before running review.");
            return;
        }

        if (currentReviewAbortController) {
            currentReviewAbortController.abort();
        }
        currentReviewAbortController = new AbortController();
        const signal = currentReviewAbortController.signal;

        // UI Loading State
        reviewBtn.disabled = true;
        reviewSpinner.style.display = "inline-block";
        reviewBtnText.textContent = "Analyzing AST & Bugs...";
        editorStatusPill.textContent = "Analyzing";
        editorStatusPill.className = "status-pill status-analyzing";

        try {
            const resp = await fetch("/api/v1/review", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    code: code,
                    language: state.language
                }),
                signal: signal
            });

            const data = await resp.json();

            if (!resp.ok || !data.success) {
                const errMsg = (data.error && data.error.message) || data.message || "Unknown server error";
                alert("Review failed: " + errMsg);
                return;
            }

            state.reviewData = data;
            state.issues = data.bugs ? data.bugs.issues : [];

            // Reset Hint Tracker for new review
            state.currentHints = {};
            state.issues.forEach(iss => {
                state.currentHints[iss.id] = 1; // Default to hint 1
            });

            // Update All Workspace Hubs
            renderReviewFindings(data);
            renderQualityScore(data);
            renderExplanation(data);
            renderASTInsight(data);
            renderComplexity(data);
            renderTestCases(data);
            renderOptimization(data);
            initVisualizer(data.visualization);
            init3DTopology(data.topology_3d);

            // Re-render line numbers to show bug markers
            updateLineNumbers(code);

            editorStatusPill.textContent = "Reviewed";
            editorStatusPill.className = "status-pill status-ready";

        } catch (err) {
            if (err.name === "AbortError") {
                // Superseded by newer review request; ignore cleanly
                return;
            }
            console.error("Review request error:", err);
            alert("Network error communicating with review engine.");
        } finally {
            reviewBtn.disabled = false;
            reviewSpinner.style.display = "none";
            reviewBtnText.textContent = "Review Code";
        }
    }

    // ==========================================================================
    // Render 1: Mentor & Progressive Hints
    // ==========================================================================

    function renderReviewFindings(data) {
        const issues = state.issues;
        issueCountPill.textContent = issues.length;

        if (issues.length === 0) {
            summaryStatusTitle.textContent = "No Critical Defects Detected";
            summaryStatusDesc.textContent = "The code passed syntax verification, static bug hunting, and runtime boundary checks!";
            issuesListContainer.innerHTML = `
                <div class="empty-state">
                    <div class="empty-icon" style="color: #34d399;">✓</div>
                    <h3>Code Passed Mentor Checks</h3>
                    <p>Clean structure, appropriate error handling, and safe memory access patterns.</p>
                </div>
            `;
            return;
        }

        summaryStatusTitle.textContent = `${issues.length} Issue(s) Detected`;
        summaryStatusDesc.textContent = "Work through the progressive hints below. Do not immediately skip to the answer!";

        let cardsHtml = "";
        issues.forEach(iss => {
            const sevClass = `severity-${iss.severity.toLowerCase()}`;
            const sevBadge = `badge-${iss.severity.toLowerCase()}`;
            const initialHint = iss.hints ? iss.hints.hint1 : "Analyze the control flow.";

            cardsHtml += `
                <div class="issue-card ${sevClass}" id="card-${iss.id}">
                    <div class="issue-header">
                        <div class="issue-tags">
                            <span class="badge-sev ${sevBadge}">${iss.severity}</span>
                            <span class="badge-line">Line ${iss.line || 1}</span>
                            <span class="badge-cat">${iss.category}</span>
                        </div>
                    </div>
                    <div class="issue-body">
                        <h4 class="issue-title">${escapeHtml(iss.problem)}</h4>
                        <p class="issue-explanation">${escapeHtml(iss.explanation)}</p>

                        <!-- Progressive Hint Box -->
                        <div class="hint-container">
                            <div class="hint-header">
                                <span class="hint-level-tag" id="hint-tag-${iss.id}">
                                    💡 Hint 1: Gentle Clue
                                </span>
                                <div class="hint-dots">
                                    <span class="hint-dot active" id="dot-${iss.id}-1"></span>
                                    <span class="hint-dot" id="dot-${iss.id}-2"></span>
                                    <span class="hint-dot" id="dot-${iss.id}-3"></span>
                                </div>
                            </div>
                            <div class="hint-text" id="hint-text-${iss.id}">
                                "${escapeHtml(initialHint)}"
                            </div>
                            <div class="hint-actions">
                                <button class="btn-hint" onclick="requestNextHint('${iss.id}')" id="btn-next-hint-${iss.id}">
                                    Next Hint ➔
                                </button>
                                <button class="btn-hint" onclick="focusLine(${iss.line || 1})">
                                    Try Again in Editor
                                </button>
                                <button class="btn-solution" onclick="requestSolution('${iss.id}')">
                                    Show Solution
                                </button>
                            </div>
                        </div>
                    </div>
                </div>
            `;
        });

        issuesListContainer.innerHTML = cardsHtml;
    }

    // Expose Progressive Hint actions globally
    window.requestNextHint = async function(bugId) {
        const curLevel = state.currentHints[bugId] || 1;
        if (curLevel >= 3) {
            alert("You have reached the final strong hint! If you're still stuck, click 'Show Solution'.");
            return;
        }

        const nextLevel = curLevel + 1;
        state.currentHints[bugId] = nextLevel;

        try {
            const resp = await fetch("/api/v1/hint", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    review_id: state.reviewData ? state.reviewData.review_id : null,
                    bug_id: bugId,
                    level: nextLevel,
                    issues: state.issues
                })
            });
            const data = await resp.json();
            if (data.success) {
                document.getElementById(`hint-tag-${bugId}`).textContent = `💡 ${data.title}`;
                document.getElementById(`hint-text-${bugId}`).textContent = `"${data.hint}"`;
                // Update dots
                for (let i = 1; i <= 3; i++) {
                    const dot = document.getElementById(`dot-${bugId}-${i}`);
                    if (dot) dot.className = `hint-dot ${i <= nextLevel ? 'active' : ''}`;
                }
                if (!data.has_next_hint) {
                    const nextBtn = document.getElementById(`btn-next-hint-${bugId}`);
                    if (nextBtn) nextBtn.style.display = "none";
                }
            }
        } catch (err) {
            console.error(err);
        }
    };

    window.requestSolution = async function(bugId) {
        try {
            const resp = await fetch("/api/v1/solution", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    review_id: state.reviewData ? state.reviewData.review_id : null,
                    bug_id: bugId,
                    issues: state.issues
                })
            });
            const data = await resp.json();
            if (data.success) {
                modalProblemTitle.textContent = data.problem;
                modalSolutionCode.textContent = data.solution.code;
                modalWhyFailed.textContent = data.solution.why_original_failed;
                modalWhyWorks.textContent = data.solution.why_new_works;

                // Configure apply button
                insertSolutionBtn.onclick = () => {
                    solutionModal.classList.remove("open");
                    // Prepend or offer code in editor
                    codeEditor.value = data.solution.code + "\n\n" + codeEditor.value;
                    codeEditor.dispatchEvent(new Event("input"));
                };

                copySolutionBtn.onclick = () => {
                    navigator.clipboard.writeText(data.solution.code);
                    flashButton(copySolutionBtn, "Copied!");
                };

                solutionModal.classList.add("open");
            } else if (data.error && data.error.code === "HINTS_INCOMPLETE") {
                alert(`⚠️ Mentor Guidance Gate:\n\n${data.error.message}\n\nPlease click 'Next Progressive Clue' to deduce the solution first!`);
            } else {
                alert(`Cannot reveal solution: ${data.error ? data.error.message : 'Unknown error'}`);
            }
        } catch (err) {
            console.error(err);
        }
    };

    window.focusLine = function(lineNum) {
        codeEditor.focus();
        const lines = codeEditor.value.split("\n");
        let charIndex = 0;
        for (let i = 0; i < Math.min(lineNum - 1, lines.length); i++) {
            charIndex += lines[i].length + 1;
        }
        codeEditor.selectionStart = charIndex;
        codeEditor.selectionEnd = charIndex + (lines[lineNum - 1] ? lines[lineNum - 1].length : 0);
        updateCursorPosition();
    };

    closeModalBtn.addEventListener("click", () => {
        solutionModal.classList.remove("open");
    });

    // ==========================================================================
    // Render 2: Quality Score Breakdown
    // ==========================================================================

    function renderQualityScore(data) {
        const score = data.score || 100;
        scoreNumberVal.textContent = score;
        scoreSummaryPill.textContent = `${score}/100`;

        // SVG Ring (circumference ~ 314)
        const offset = 314 - (314 * (score / 100));
        scoreRingCircle.style.strokeDashoffset = offset;

        // Color gradient
        if (score >= 85) {
            scoreRingCircle.style.stroke = "#10b981";
            scoreVerdict.textContent = "Production Grade: High Quality";
        } else if (score >= 70) {
            scoreRingCircle.style.stroke = "#f59e0b";
            scoreVerdict.textContent = "Moderate: Functional with Risks";
        } else {
            scoreRingCircle.style.stroke = "#ef4444";
            scoreVerdict.textContent = "Attention Needed: Defects Present";
        }

        // Category Breakdown
        const cats = data.score_breakdown || {};
        for (const [key, val] of Object.entries(cats)) {
            const textElem = document.getElementById(`metricVal-${key}`);
            const barElem = document.getElementById(`metricBar-${key}`);
            if (textElem) textElem.textContent = `${val}%`;
            if (barElem) barElem.style.width = `${val}%`;
        }
    }

    // ==========================================================================
    // Render 3: Code Explanation
    // ==========================================================================

    function renderExplanation(data) {
        const exp = data.explanation || {};
        explPurpose.textContent = exp.purpose || "Algorithm performs sequential data operations.";
        explAlgorithm.textContent = exp.algorithm || "Standard conditional execution.";

        if (exp.data_structures && exp.data_structures.length) {
            explDataStructures.innerHTML = exp.data_structures.map(d => `<span class="data-tag">${escapeHtml(d)}</span>`).join("");
        } else {
            explDataStructures.innerHTML = `<span class="data-tag">Primitive Variables</span>`;
        }

        if (exp.step_by_step && exp.step_by_step.length) {
            explStepList.innerHTML = exp.step_by_step.map(s => `<li>${escapeHtml(s)}</li>`).join("");
        }

        explMentorNote.textContent = exp.mentor_note || "Focus on robust edge-case coverage to write resilient software.";
        explProviderBadge.textContent = `Generated via: ${exp.provider || 'Offline Intelligence Engine'}`;
    }

    // ==========================================================================
    // Render 4: AST Insight
    // ==========================================================================

    function renderASTInsight(data) {
        const astData = data.ast || {};
        const metrics = astData.metrics || {};

        astFuncCount.textContent = metrics.functions_count || 0;
        astLoopCount.textContent = metrics.loops_count || 0;
        astBranchCount.textContent = metrics.branches_count || 0;
        astDepthCount.textContent = metrics.max_nesting_depth || 0;

        // Flow Pipeline Blocks
        const chain = astData.flow_chain || [];
        if (chain.length) {
            let flowHtml = "";
            chain.forEach((item, idx) => {
                flowHtml += `
                    <div class="flow-node-badge">
                        <span class="flow-node-cat">${item.type}</span>
                        <span class="flow-node-lbl">${escapeHtml(item.label)}</span>
                    </div>
                `;
                if (idx < chain.length - 1) {
                    flowHtml += `<span class="flow-connector">➔</span>`;
                }
            });
            astFlowPipeline.innerHTML = flowHtml;
        } else {
            astFlowPipeline.innerHTML = `<span style="font-size: 11px; color: var(--text-muted);">No composite control blocks found.</span>`;
        }

        // Nodes Table
        const nodes = astData.flow_nodes || [];
        if (nodes.length) {
            let tableHtml = "";
            nodes.forEach(n => {
                tableHtml += `
                    <div class="ast-row">
                        <span class="ast-row-line">Ln ${n.line}</span>
                        <span class="ast-row-type">${n.type}</span>
                        <span class="ast-row-desc">${escapeHtml(n.label)}</span>
                        <button class="btn-text-sm" onclick="focusLine(${n.line})">Jump</button>
                    </div>
                `;
            });
            astNodesList.innerHTML = tableHtml;
        } else {
            astNodesList.innerHTML = `<div style="padding: 10px; color: var(--text-muted);">AST nodes generated on review.</div>`;
        }
    }

    // ==========================================================================
    // Render 5: Complexity Analysis
    // ==========================================================================

    function renderComplexity(data) {
        const comp = data.complexity || {};
        compTimeVal.textContent = comp.time_complexity || "O(1)";
        compTimeReason.textContent = comp.reasoning || "Constant operations.";

        compSpaceVal.textContent = comp.space_complexity || "O(1)";
        compSpaceReason.textContent = comp.space_details || "Constant auxiliary memory.";

        scenBestBound.textContent = comp.best_case || "O(1)";
        scenAvgBound.textContent = comp.average_case || comp.time_complexity || "O(n)";
        scenWorstBound.textContent = comp.worst_case || comp.time_complexity || "O(n)";

        const tcData = data.test_cases || {};
        const scen = tcData.case_scenarios || {};
        scenBestDesc.textContent = (scen.best_case && scen.best_case.reason) ? scen.best_case.reason : "Optimal scenario input.";
        scenAvgDesc.textContent = (scen.average_case && scen.average_case.reason) ? scen.average_case.reason : "Standard distribution input.";
        scenWorstDesc.textContent = (scen.worst_case && scen.worst_case.reason) ? scen.worst_case.reason : "Maximum operations input.";

        if (comp.hotspots && comp.hotspots.length) {
            compHotspotsList.innerHTML = comp.hotspots.map(h => `<li>${escapeHtml(h)}</li>`).join("");
        } else {
            compHotspotsList.innerHTML = `<li>No algorithmic bottlenecks found.</li>`;
        }
    }

    // ==========================================================================
    // Render 6: Test Cases Generator & Safe Runner
    // ==========================================================================

    function renderTestCases(data) {
        const tcData = data.test_cases || {};
        const cases = tcData.test_cases || [];

        tcTotalCount.textContent = cases.length;
        tcPassedCount.textContent = "0";
        tcFailedCount.textContent = "0";

        if (!cases.length) {
            testCardsContainer.innerHTML = `<div class="empty-state">No test cases generated.</div>`;
            return;
        }

        let html = "";
        cases.forEach(tc => {
            html += `
                <div class="test-card" id="card-${tc.id}">
                    <div class="test-card-header">
                        <span class="test-cat-tag">${tc.category}</span>
                        <span class="test-status-badge" id="status-badge-${tc.id}">PENDING</span>
                    </div>
                    <p style="font-size: 12px; color: var(--text-secondary); margin-bottom: 8px;">
                        ${escapeHtml(tc.description)}
                    </p>
                    <div class="test-grid-fields">
                        <div>
                            <span class="test-field-lbl">INPUT</span>
                            <div>${escapeHtml(tc.input)}</div>
                        </div>
                        <div>
                            <span class="test-field-lbl">EXPECTED</span>
                            <div>${escapeHtml(tc.expected)}</div>
                        </div>
                    </div>
                    <div style="margin-top: 6px; font-family: var(--font-mono); font-size: 11px; display: none;" id="actual-row-${tc.id}">
                        <span class="test-field-lbl">ACTUAL:</span> <span id="actual-val-${tc.id}"></span>
                    </div>
                </div>
            `;
        });
        testCardsContainer.innerHTML = html;
    }

    runAllTestsBtn.addEventListener("click", async () => {
        if (!state.reviewData || !state.reviewData.test_cases) {
            alert("Please run 'Review Code' first to generate test cases.");
            return;
        }

        runAllTestsBtn.disabled = true;
        runAllTestsBtn.textContent = "Executing in Sandbox...";

        try {
            const resp = await fetch("/api/v1/run-tests", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    code: codeEditor.value,
                    language: state.language,
                    test_cases: state.reviewData.test_cases.test_cases,
                    function_name: state.reviewData.test_cases.function_name
                })
            });
            const data = await resp.json();

            if (data.success) {
                tcPassedCount.textContent = data.passed_count;
                tcFailedCount.textContent = data.total_count - data.passed_count;

                data.results.forEach(res => {
                    const badge = document.getElementById(`status-badge-${res.id}`);
                    const actRow = document.getElementById(`actual-row-${res.id}`);
                    const actVal = document.getElementById(`actual-val-${res.id}`);

                    if (badge) {
                        badge.textContent = res.status;
                        badge.className = `test-status-badge ${res.passed ? 'pass' : (res.status === 'ERROR' ? 'error' : 'fail')}`;
                    }
                    if (actRow && actVal) {
                        actRow.style.display = "block";
                        actVal.textContent = res.actual + (res.execution_time_ms ? ` (${res.execution_time_ms}ms)` : "");
                    }
                });
            }
        } catch (err) {
            console.error(err);
        } finally {
            runAllTestsBtn.disabled = false;
            runAllTestsBtn.innerHTML = `
                <svg viewBox="0 0 24 24" width="15" height="15" fill="none" stroke="currentColor" stroke-width="2">
                    <polyline points="20 6 9 17 4 12"></polyline>
                </svg>
                <span>Run All Test Cases</span>
            `;
        }
    });

    // ==========================================================================
    // Render 7: Optimization Engine
    // ==========================================================================

    function renderOptimization(data) {
        const opt = data.optimization || {};
        optCurrentComp.textContent = opt.current_approach ? opt.current_approach.split(" ")[0] : "O(n²)";
        optTargetComp.textContent = opt.possible_improvement ? opt.possible_improvement.split(" ")[0] : "O(n)";
        optTitle.textContent = opt.title || "Optimization Opportunity";
        optSummary.textContent = opt.summary || "No active bottlenecks.";

        optWhatChanges.textContent = opt.what_changes || "--";
        optWhyImproves.textContent = opt.why_it_improves || "--";
        optTradeOffs.textContent = opt.trade_offs || "--";
        optWhenUseful.textContent = opt.when_useful || "--";

        if (opt.diff) {
            optimizedDiffPre.textContent = opt.diff;
            toggleOptimizedCodeBtn.style.display = "inline-flex";
        } else if (opt.optimized_code) {
            optimizedDiffPre.textContent = opt.optimized_code;
            toggleOptimizedCodeBtn.style.display = "inline-flex";
        } else {
            toggleOptimizedCodeBtn.style.display = "none";
        }

        applyOptimizedBtn.onclick = () => {
            if (opt.optimized_code) {
                codeEditor.value = opt.optimized_code;
                codeEditor.dispatchEvent(new Event("input"));
                flashButton(applyOptimizedBtn, "Applied!");
            }
        };
    }

    toggleOptimizedCodeBtn.addEventListener("click", () => {
        const isHidden = optimizedCodeWrapper.style.display === "none";
        optimizedCodeWrapper.style.display = isHidden ? "block" : "none";
        toggleOptimizedCodeBtn.textContent = isHidden ? "Hide Optimized Code" : "Show Optimized Code";
    });

    // ==========================================================================
    // Render 8: Visual Code Execution Engine
    // ==========================================================================

    function initVisualizer(visData) {
        if (state.visualizer.timer) {
            clearInterval(state.visualizer.timer);
            state.visualizer.timer = null;
        }
        if (!visData || visData.supported === false || !visData.frames || !visData.frames.length) {
            const reason = (visData && visData.reason) || "Visualizer ready. Review code to generate interactive steps.";
            visStage.innerHTML = `<div class="vis-empty">${escapeHtml(reason)}</div>`;
            state.visualizer.frames = [];
            state.visualizer.totalSteps = 0;
            state.visualizer.currentStep = 0;
            state.visualizer.isPlaying = false;
            updatePlayPauseUI();
            visAlgoTitle.textContent = (visData && visData.algorithm) || "Algorithm Visualization";
            visTotalSteps.textContent = "0";
            visCurrentStep.textContent = "0";
            return;
        }

        state.visualizer.frames = visData.frames;
        state.visualizer.totalSteps = visData.frames.length;
        state.visualizer.currentStep = 0;
        state.visualizer.isPlaying = false;
        updatePlayPauseUI();

        visAlgoTitle.textContent = visData.algorithm || "Algorithm Visualization";
        visTotalSteps.textContent = state.visualizer.totalSteps;

        renderCurrentFrame();
    }

    function renderCurrentFrame() {
        const step = state.visualizer.currentStep;
        const frames = state.visualizer.frames;
        if (!frames || !frames[step]) return;

        const frame = frames[step];
        visCurrentStep.textContent = step + 1;
        visStepMessage.textContent = frame.message || `Step ${step + 1} execution`;
        visCodeLine.textContent = frame.code_line || "";

        if (frame.type === "sorting") {
            renderSortingFrame(frame);
        } else if (frame.type === "binary_search") {
            renderBinarySearchFrame(frame);
        } else if (frame.type === "call_stack") {
            renderCallStackFrame(frame);
        } else if (frame.type === "two_sum") {
            renderTwoSumFrame(frame);
        } else {
            renderGenericArrayFrame(frame);
        }
    }

    function renderSortingFrame(frame) {
        const arr = frame.array;
        const maxVal = Math.max(...arr, 1);
        const comparing = frame.comparing || [];
        const sortedIndices = new Set(frame.sorted_indices || []);

        let html = `<div class="vis-bars-container">`;
        arr.forEach((val, idx) => {
            const heightPercent = Math.max(15, (val / maxVal) * 100);
            let barClass = "vis-bar";
            if (sortedIndices.has(idx)) {
                barClass += " settled";
            } else if (frame.swapping && comparing.includes(idx)) {
                barClass += " swapping";
            } else if (comparing.includes(idx)) {
                barClass += " comparing";
            }

            html += `
                <div class="vis-bar-wrapper">
                    <span class="vis-bar-val">${val}</span>
                    <div class="${barClass}" style="height: ${heightPercent}%;"></div>
                    <span class="vis-bar-idx">[${idx}]</span>
                </div>
            `;
        });
        html += `</div>`;
        visStage.innerHTML = html;
    }

    function renderBinarySearchFrame(frame) {
        const arr = frame.array;
        let html = `<div class="vis-bs-cells">`;
        arr.forEach((val, idx) => {
            let cls = "vis-bs-cell";
            let pointer = "";

            if (idx === frame.mid) {
                cls += frame.found ? " found" : " mid";
                pointer = "MID";
            } else if (idx === frame.low && idx === frame.high) {
                pointer = "LOW/HI";
            } else if (idx === frame.low) {
                pointer = "LOW";
            } else if (idx === frame.high) {
                pointer = "HIGH";
            }

            if (frame.low !== null && (idx < frame.low || idx > frame.high)) {
                cls += " discarded";
            }

            html += `
                <div class="${cls}">
                    <span>${val}</span>
                    ${pointer ? `<span class="vis-bs-pointer">${pointer}</span>` : ''}
                </div>
            `;
        });
        html += `</div>`;
        visStage.innerHTML = html;
    }

    function renderCallStackFrame(frame) {
        const stack = frame.stack || [];
        let html = `<div class="vis-stack-column">`;
        stack.forEach(fn => {
            html += `<div class="vis-stack-frame">${escapeHtml(fn)}</div>`;
        });
        html += `</div>`;
        visStage.innerHTML = html;
    }

    function renderTwoSumFrame(frame) {
        const arr = frame.array;
        let html = `<div class="vis-bs-cells">`;
        arr.forEach((val, idx) => {
            let cls = "vis-bs-cell";
            if (idx === frame.current_index) cls += " mid";
            if (frame.found_pair && frame.found_pair.includes(idx)) cls += " found";

            html += `<div class="${cls}"><span>${val}</span><span class="vis-bar-idx">[${idx}]</span></div>`;
        });
        html += `</div>`;
        visStage.innerHTML = html;
    }

    function renderGenericArrayFrame(frame) {
        const arr = frame.array || [];
        let html = `<div class="vis-bs-cells">`;
        arr.forEach((val, idx) => {
            let cls = "vis-bs-cell";
            if (idx === frame.current_index) cls += " mid";
            html += `<div class="${cls}"><span>${val}</span></div>`;
        });
        html += `</div>`;
        visStage.innerHTML = html;
    }

    function updatePlayPauseUI() {
        if (state.visualizer.isPlaying) {
            playIcon.style.display = "none";
            pauseIcon.style.display = "block";
        } else {
            playIcon.style.display = "block";
            pauseIcon.style.display = "none";
        }
    }

    visPlayPauseBtn.addEventListener("click", () => {
        if (state.visualizer.isPlaying) {
            pauseVisualization();
        } else {
            playVisualization();
        }
    });

    function playVisualization() {
        if (state.visualizer.timer) {
            clearInterval(state.visualizer.timer);
            state.visualizer.timer = null;
        }
        if (state.visualizer.currentStep >= state.visualizer.totalSteps - 1) {
            state.visualizer.currentStep = 0;
        }
        state.visualizer.isPlaying = true;
        updatePlayPauseUI();

        state.visualizer.timer = setInterval(() => {
            if (state.visualizer.currentStep < state.visualizer.totalSteps - 1) {
                state.visualizer.currentStep++;
                renderCurrentFrame();
            } else {
                pauseVisualization();
            }
        }, state.visualizer.speedMs);
    }

    function pauseVisualization() {
        state.visualizer.isPlaying = false;
        if (state.visualizer.timer) {
            clearInterval(state.visualizer.timer);
            state.visualizer.timer = null;
        }
        updatePlayPauseUI();
    }

    visStepForwardBtn.addEventListener("click", () => {
        pauseVisualization();
        if (state.visualizer.currentStep < state.visualizer.totalSteps - 1) {
            state.visualizer.currentStep++;
            renderCurrentFrame();
        }
    });

    visStepBackBtn.addEventListener("click", () => {
        pauseVisualization();
        if (state.visualizer.currentStep > 0) {
            state.visualizer.currentStep--;
            renderCurrentFrame();
        }
    });

    visRestartBtn.addEventListener("click", () => {
        pauseVisualization();
        state.visualizer.currentStep = 0;
        renderCurrentFrame();
    });

    visSpeedSelect.addEventListener("change", (e) => {
        state.visualizer.speedMs = parseInt(e.target.value, 10);
        if (state.visualizer.isPlaying) {
            pauseVisualization();
            playVisualization();
        }
    });

    // ==========================================================================
    // ==========================================================================
    // Sandbox Runner (Direct Execution & Topics Cockpit)
    // ==========================================================================

    const sandboxTabBtns = document.querySelectorAll(".sandbox-tab-btn");
    const sandboxPanels = {
        output: document.getElementById("sbox-panel-output"),
        topics: document.getElementById("sbox-panel-topics"),
        telemetry: document.getElementById("sbox-panel-telemetry"),
        stdin: document.getElementById("sbox-panel-stdin")
    };
    const sboxTopicCount = document.getElementById("sboxTopicCount");
    const stdoutStatusTag = document.getElementById("stdoutStatusTag");
    const stderrStatusTag = document.getElementById("stderrStatusTag");
    const sandboxTopicsContainer = document.getElementById("sandboxTopicsContainer");
    const telemExitCode = document.getElementById("telemExitCode");
    const telemRuntime = document.getElementById("telemRuntime");
    const telemMemory = document.getElementById("telemMemory");
    const telemSafety = document.getElementById("telemSafety");
    const telemExitDesc = document.getElementById("telemExitDesc");
    const telemRuntimeDesc = document.getElementById("telemRuntimeDesc");

    // Sub-tab switching inside sandbox
    sandboxTabBtns.forEach(btn => {
        btn.addEventListener("click", () => {
            const target = btn.dataset.sboxtab;
            sandboxTabBtns.forEach(b => b.classList.remove("active"));
            Object.values(sandboxPanels).forEach(p => p && p.classList.remove("active"));
            btn.classList.add("active");
            if (sandboxPanels[target]) {
                sandboxPanels[target].classList.add("active");
            }
        });
    });

    // Quick STDIN Presets
    document.querySelectorAll(".stdin-preset-btn").forEach(btn => {
        btn.addEventListener("click", () => {
            stdinInput.value = btn.dataset.val || "";
            // Switch back to output or stay
            stdinInput.focus();
        });
    });

    function renderSandboxTopics(topics) {
        if (!sandboxTopicsContainer) return;
        const topicList = topics || [];
        if (sboxTopicCount) sboxTopicCount.textContent = topicList.length;

        if (topicList.length === 0) {
            sandboxTopicsContainer.innerHTML = `
                <div class="empty-topics-state">No computational topics flagged for this run.</div>
            `;
            return;
        }

        let html = "";
        topicList.forEach(t => {
            const borderCol = t.color || "#38bdf8";
            html += `
                <div class="sandbox-topic-card" style="border-left-color: ${borderCol}">
                    <div class="topic-top-row">
                        <div class="topic-title-wrap">
                            <span class="topic-icon">${t.icon || '📌'}</span>
                            <span class="topic-name">${escapeHtml(t.name)}</span>
                        </div>
                        <span class="topic-badge" style="background: ${borderCol}20; color: ${borderCol};">${escapeHtml(t.badge || t.category)}</span>
                    </div>
                    <div class="topic-summary">${escapeHtml(t.summary)}</div>
                    <div class="topic-details">${escapeHtml(t.details)}</div>
                </div>
            `;
        });
        sandboxTopicsContainer.innerHTML = html;
    }

    function renderSandboxTelemetry(telemetry) {
        if (!telemetry) return;
        if (telemExitCode) {
            telemExitCode.textContent = telemetry.exit_code === 0 ? "0 (SUCCESS)" : `${telemetry.exit_code} (ERROR)`;
            telemExitCode.style.color = telemetry.exit_code === 0 ? "#10b981" : "#ef4444";
        }
        if (telemRuntime) {
            telemRuntime.textContent = telemetry.execution_time_ms ? `${telemetry.execution_time_ms}ms` : "< 1ms";
        }
        if (telemMemory) {
            telemMemory.textContent = telemetry.memory_tier || "Heap Stack (< 64MB)";
        }
        if (telemSafety) {
            telemSafety.textContent = telemetry.safety_audit.includes("PASSED") ? "PASSED (SECURED)" : "FLAGGED";
            telemSafety.style.color = telemetry.safety_audit.includes("PASSED") ? "#10b981" : "#ef4444";
        }
        if (telemExitDesc) {
            telemExitDesc.textContent = `Language: ${telemetry.language.toUpperCase()} • Mode: ${telemetry.isolation_mode}`;
        }
    }

    runCodeBtn.addEventListener("click", async () => {
        const code = codeEditor.value;
        if (!code.trim()) {
            alert("No code to run. Please type or paste code into the editor.");
            return;
        }

        runCodeBtn.disabled = true;
        consoleStatusBadge.textContent = `Building & Running (${state.language.toUpperCase()})...`;
        consoleStatusBadge.style.color = "#fbbf24";
        stdoutText.textContent = `[SANDBOX] Initializing isolated subprocess compiler for ${state.language.toUpperCase()}...`;
        stderrText.textContent = "";
        if (stdoutStatusTag) stdoutStatusTag.textContent = "Compiling...";
        if (stderrStatusTag) stderrStatusTag.textContent = "Monitoring...";

        try {
            const resp = await fetch("/api/v1/execute", {
                method: "POST",
                headers: { "Content-Type": "application/json" },
                body: JSON.stringify({
                    code: code,
                    language: state.language,
                    stdin: stdinInput.value
                })
            });
            const data = await resp.json();

            const statusText = data.status || (data.success ? "PASSED" : "ERROR");
            consoleStatusBadge.textContent = statusText;
            consoleStatusBadge.style.color = data.success ? "#34d399" : (statusText === "COMPILE_ERROR" ? "#fb7185" : "#f87171");
            execDuration.textContent = data.execution_time_ms ? `${data.execution_time_ms}ms` : "";

            if (stdoutStatusTag) stdoutStatusTag.textContent = data.success ? "Exit Code 0" : "Non-Zero Exit";
            if (stderrStatusTag) stderrStatusTag.textContent = data.stderr ? "Diagnostics Logged" : "Clean Stream";

            if (data.stdout && data.stdout.trim()) {
                stdoutText.textContent = data.stdout;
            } else if (data.success) {
                stdoutText.textContent = "(Program exited with code 0. No standard output was printed.)";
            } else {
                stdoutText.textContent = "(No standard output generated due to execution / compilation failure.)";
            }

            stderrText.textContent = data.stderr || "";

            // Render structured topics and telemetry
            renderSandboxTopics(data.topics_involved);
            renderSandboxTelemetry(data.runtime_telemetry);

            // Auto-scroll console output
            const consoleContent = document.getElementById("consoleContent");
            if (consoleContent) consoleContent.scrollTop = consoleContent.scrollHeight;

        } catch (err) {
            stderrText.textContent = "Execution request error: " + err.message;
            consoleStatusBadge.textContent = "COMMUNICATION_ERROR";
            consoleStatusBadge.style.color = "#ef4444";
        } finally {
            runCodeBtn.disabled = false;
        }
    });

    clearConsoleBtn.addEventListener("click", () => {
        stdoutText.textContent = "// Output cleared.";
        stderrText.textContent = "";
        execDuration.textContent = "";
        consoleStatusBadge.textContent = "Idle";
        consoleStatusBadge.style.color = "var(--text-muted)";
        if (stdoutStatusTag) stdoutStatusTag.textContent = "Buffer Ready";
        if (stderrStatusTag) stderrStatusTag.textContent = "Clean";
    });

    // ==========================================================================
    // Review History Drawer
    // ==========================================================================

    historyToggleBtn.addEventListener("click", async () => {
        historyDrawer.classList.toggle("open");
        if (historyDrawer.classList.contains("open")) {
            loadHistory();
        }
    });

    closeHistoryBtn.addEventListener("click", () => {
        historyDrawer.classList.remove("open");
    });

    const clearAllHistoryBtn = document.getElementById("clearAllHistoryBtn");
    if (clearAllHistoryBtn) {
        clearAllHistoryBtn.addEventListener("click", async () => {
            if (!confirm("Are you sure you want to permanently delete all stored review history?")) return;
            try {
                const resp = await fetch("/api/v1/history", { method: "DELETE" });
                const data = await resp.json();
                if (data.success) {
                    loadHistory();
                }
            } catch (err) {
                console.error("Failed to delete all history:", err);
            }
        });
    }

    async function loadHistory() {
        historyList.innerHTML = `<div class="history-loading">Fetching saved reviews...</div>`;
        try {
            const resp = await fetch("/api/v1/history?limit=25");
            const data = await resp.json();
            if (data.success && data.history && data.history.length) {
                let html = "";
                data.history.forEach(item => {
                    const dt = new Date(item.timestamp).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
                    html += `
                        <div class="history-item-card" onclick="restoreHistoryItem(${item.id})">
                            <div style="display: flex; justify-content: space-between; align-items: flex-start;">
                                <div class="history-item-title">${escapeHtml(item.title)}</div>
                                <button class="btn-text-sm" style="color: #ef4444; padding: 2px 6px; font-size: 11px;" title="Delete this review" onclick="deleteHistoryItem(event, ${item.id})">✕</button>
                            </div>
                            <div class="history-item-meta">
                                <span>${item.language.toUpperCase()} • ${item.issue_count} issue(s)</span>
                                <span>Score: ${item.score}/100 • ${dt}</span>
                            </div>
                        </div>
                    `;
                });
                historyList.innerHTML = html;
            } else {
                historyList.innerHTML = `<div class="empty-state">No past reviews saved yet.</div>`;
            }
        } catch (err) {
            historyList.innerHTML = `<div class="empty-state">Failed to load history.</div>`;
        }
    }

    window.deleteHistoryItem = async function(event, id) {
        event.stopPropagation();
        if (!confirm(`Delete review #${id}?`)) return;
        try {
            const resp = await fetch(`/api/v1/history/${id}`, { method: "DELETE" });
            const data = await resp.json();
            if (data.success) {
                loadHistory();
            }
        } catch (err) {
            console.error("Failed to delete review:", err);
        }
    };

    window.restoreHistoryItem = async function(id) {
        try {
            const resp = await fetch(`/api/v1/history/${id}`);
            const data = await resp.json();
            if (data.success && data.review) {
                const r = data.review;
                codeEditor.value = r.code;
                state.code = r.code;
                state.language = r.language;
                languageSelect.value = r.language;
                updateLineNumbers(r.code);
                updateSyntaxHighlight(r.code);

                if (r.review_data) {
                    state.reviewData = r.review_data;
                    state.issues = r.review_data.bugs ? r.review_data.bugs.issues : [];
                    renderReviewFindings(r.review_data);
                    renderQualityScore(r.review_data);
                    renderExplanation(r.review_data);
                    renderASTInsight(r.review_data);
                    renderComplexity(r.review_data);
                    renderTestCases(r.review_data);
                    renderOptimization(r.review_data);
                    initVisualizer(r.review_data.visualization);
                    init3DTopology(r.review_data.topology_3d);
                }

                historyDrawer.classList.remove("open");
            }
        } catch (err) {
            console.error(err);
        }
    };

    // ==========================================================================
    // Panel 9: 3D Code Spatial Architecture & Moving Control Flow Engine
    // ==========================================================================

    // ==========================================================================
    // Panel 9: Program Control Flow & Execution Pipeline (Clean 2D Graph & Timeline)
    // ==========================================================================

    const threedNodeCount = document.getElementById("threedNodeCount");
    const threedConduitCount = document.getElementById("threedConduitCount");
    const flowchartNodesContainer = document.getElementById("flowchartNodesContainer");
    const flowTimelineContainer = document.getElementById("flowTimelineContainer");

    const threedNodeHud = document.getElementById("threedNodeHud");
    const hudNodeCategory = document.getElementById("hudNodeCategory");
    const hudNodeLabel = document.getElementById("hudNodeLabel");
    const hudNodeDesc = document.getElementById("hudNodeDesc");
    const hudNodeSnippet = document.getElementById("hudNodeSnippet");
    const hudNodeLine = document.getElementById("hudNodeLine");
    const hudNodeComplexity = document.getElementById("hudNodeComplexity");
    const hudJumpBtn = document.getElementById("hudJumpBtn");
    const closeNodeHudBtn = document.getElementById("closeNodeHudBtn");

    // Flow Player DOM Elements
    const playFlow3DBtn = document.getElementById("playFlow3DBtn");
    const playFlow3DIcon = document.getElementById("playFlow3DIcon");
    const pauseFlow3DIcon = document.getElementById("pauseFlow3DIcon");
    const playFlow3DLabel = document.getElementById("playFlow3DLabel");
    const stepBack3DBtn = document.getElementById("stepBack3DBtn");
    const stepForward3DBtn = document.getElementById("stepForward3DBtn");
    const restart3DFlowBtn = document.getElementById("restart3DFlowBtn");
    const flow3DSpeedSelect = document.getElementById("flow3DSpeedSelect");
    const flow3DStepBadge = document.getElementById("flow3DStepBadge");
    const flow3DStepMessage = document.getElementById("flow3DStepMessage");

    let flowGraphState = {
        nodes: [],
        edges: [],
        steps: [],
        currentStep: 0,
        isPlaying: false,
        timer: null,
        speedMs: 700
    };

    function init3DTopology(topoData) {
        if (!topoData) return;

        flowGraphState.nodes = topoData.nodes || [];
        flowGraphState.edges = topoData.edges || [];
        flowGraphState.steps = topoData.execution_steps || [];
        flowGraphState.currentStep = 0;

        if (threedNodeCount) threedNodeCount.textContent = topoData.total_nodes || flowGraphState.nodes.length || 0;
        if (threedConduitCount) threedConduitCount.textContent = topoData.total_conduits || flowGraphState.edges.length || 0;

        pause3DFlow();
        renderControlFlowGraph(topoData);
        updateFlowPlayerUI(0);
    }

    function renderControlFlowGraph(topoData) {
        if (!flowchartNodesContainer || !flowTimelineContainer) return;

        const nodes = topoData.nodes || [];
        const edges = topoData.edges || [];
        const steps = topoData.execution_steps || [];

        // 1. Build Flowchart Nodes
        if (nodes.length === 0) {
            flowchartNodesContainer.innerHTML = `
                <div class="empty-state" style="padding: 24px; text-align: center;">
                    <p style="color: var(--text-muted); font-size: 13px;">No control flow nodes detected for the current code snippet.</p>
                </div>
            `;
        } else {
            let html = "";
            nodes.forEach((node, idx) => {
                const cat = (node.category || "OPERATION").toUpperCase();
                const color = node.color || "#38bdf8";
                const line = node.line || 1;
                const snippet = node.snippet || node.label || "";
                const desc = node.description || "";
                const complexity = node.complexity || "O(1)";

                html += `
                    <div class="flow-node-card" id="flowNode-${escapeHtml(node.id)}" data-node-id="${escapeHtml(node.id)}" data-line="${line}">
                        <div class="flow-node-header-row">
                            <span class="flow-node-cat" style="background: ${color}22; color: ${color}; border: 1px solid ${color}55;">${escapeHtml(cat)}</span>
                            <span class="flow-node-line">Line ${line} • ${escapeHtml(complexity)}</span>
                        </div>
                        <div class="flow-node-code">${escapeHtml(snippet)}</div>
                        <div class="flow-node-desc">${escapeHtml(desc)}</div>
                    </div>
                `;

                // Check outgoing edge for arrow connector to next block
                if (idx < nodes.length - 1) {
                    const outgoing = edges.find(e => e.from === node.id && e.to === nodes[idx + 1].id) || edges.find(e => e.from === node.id);
                    let arrowLabel = "";
                    let arrowClass = "";
                    let arrowIcon = `
                        <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" stroke-width="2.2" stroke-linecap="round" stroke-linejoin="round">
                            <line x1="12" y1="5" x2="12" y2="19"></line>
                            <polyline points="19 12 12 19 5 12"></polyline>
                        </svg>
                    `;

                    if (outgoing) {
                        if (outgoing.flowType === "true_branch") {
                            arrowLabel = "[TRUE PATH]";
                            arrowClass = "true-path";
                        } else if (outgoing.flowType === "false_branch") {
                            arrowLabel = "[FALSE PATH]";
                            arrowClass = "false-path";
                        } else if (outgoing.flowType === "loopback") {
                            arrowLabel = "↺ [LOOP ITERATION]";
                            arrowClass = "loopback-path";
                        }
                    }

                    html += `
                        <div class="flow-arrow-connector">
                            ${arrowLabel ? `<span class="flow-arrow-label ${arrowClass}">${escapeHtml(arrowLabel)}</span>` : ""}
                            ${arrowIcon}
                        </div>
                    `;
                }
            });

            flowchartNodesContainer.innerHTML = html;

            // Attach card click handlers
            nodes.forEach(node => {
                const el = document.getElementById(`flowNode-${node.id}`);
                if (el) {
                    el.addEventListener("click", () => {
                        showNodeHud(node);
                        if (node.line) focusLine(node.line);
                    });
                }
            });
        }

        // 2. Build Chronological Execution Steps Timeline
        if (steps.length === 0) {
            flowTimelineContainer.innerHTML = `
                <div class="empty-state" style="padding: 24px; text-align: center;">
                    <p style="color: var(--text-muted); font-size: 13px;">No execution trace steps available.</p>
                </div>
            `;
        } else {
            let timelineHtml = "";
            steps.forEach((step, idx) => {
                timelineHtml += `
                    <div class="timeline-step-card" id="timelineStep-${idx}" data-step-idx="${idx}" data-node-id="${escapeHtml(step.node_id || '')}">
                        <div class="timeline-step-top">
                            <span class="timeline-step-num">Step ${idx + 1}</span>
                            <span class="flow-node-line">Line ${step.line || 1}</span>
                        </div>
                        <div class="timeline-step-title">${escapeHtml(step.title || 'Instruction')}</div>
                        <div class="timeline-step-desc">${escapeHtml(step.description || '')}</div>
                    </div>
                `;
            });

            flowTimelineContainer.innerHTML = timelineHtml;

            // Attach timeline step click handlers
            steps.forEach((step, idx) => {
                const stepEl = document.getElementById(`timelineStep-${idx}`);
                if (stepEl) {
                    stepEl.addEventListener("click", () => {
                        pause3DFlow();
                        flowGraphState.currentStep = idx;
                        updateFlowPlayerUI(idx);
                    });
                }
            });
        }
    }

    function updateFlowPlayerUI(stepIdx) {
        const steps = flowGraphState.steps;
        if (!steps || steps.length === 0) {
            if (flow3DStepBadge) flow3DStepBadge.textContent = "Step 0 / 0";
            if (flow3DStepMessage) flow3DStepMessage.innerHTML = "No control flow steps available for current code.";
            return;
        }

        const safeIdx = Math.max(0, Math.min(stepIdx, steps.length - 1));
        const cur = steps[safeIdx];
        if (flow3DStepBadge) flow3DStepBadge.textContent = `Step ${safeIdx + 1} / ${steps.length}`;
        if (flow3DStepMessage) {
            flow3DStepMessage.innerHTML = `<strong>${escapeHtml(cur.title)}</strong> (Line ${cur.line}): ${escapeHtml(cur.description)}`;
        }

        // 1. Highlight active node in flowchart
        document.querySelectorAll(".flow-node-card").forEach(el => el.classList.remove("active"));
        if (cur.node_id) {
            const activeCard = document.getElementById(`flowNode-${cur.node_id}`);
            if (activeCard) {
                activeCard.classList.add("active");
                activeCard.scrollIntoView({ behavior: "smooth", block: "nearest" });
            }
        }

        // 2. Highlight active step in timeline
        document.querySelectorAll(".timeline-step-card").forEach(el => el.classList.remove("active"));
        const activeTimelineStep = document.getElementById(`timelineStep-${safeIdx}`);
        if (activeTimelineStep) {
            activeTimelineStep.classList.add("active");
            activeTimelineStep.scrollIntoView({ behavior: "smooth", block: "nearest" });
        }

        // 3. Highlight line in Code Editor
        if (cur.line) {
            focusLine(cur.line);
        }
    }

    function play3DFlow() {
        const steps = flowGraphState.steps;
        if (!steps || steps.length === 0) return;

        flowGraphState.isPlaying = true;
        if (playFlow3DIcon) playFlow3DIcon.style.display = "none";
        if (pauseFlow3DIcon) pauseFlow3DIcon.style.display = "inline-block";
        if (playFlow3DLabel) playFlow3DLabel.textContent = "Pause Flow";
        if (playFlow3DBtn) playFlow3DBtn.classList.add("active");

        if (flowGraphState.currentStep >= steps.length - 1) {
            flowGraphState.currentStep = 0;
        }

        flowGraphState.timer = setInterval(() => {
            flowGraphState.currentStep++;
            if (flowGraphState.currentStep >= steps.length) {
                flowGraphState.currentStep = 0;
            }
            updateFlowPlayerUI(flowGraphState.currentStep);
        }, flowGraphState.speedMs);
    }

    function pause3DFlow() {
        flowGraphState.isPlaying = false;
        if (flowGraphState.timer) {
            clearInterval(flowGraphState.timer);
            flowGraphState.timer = null;
        }
        if (playFlow3DIcon) playFlow3DIcon.style.display = "inline-block";
        if (pauseFlow3DIcon) pauseFlow3DIcon.style.display = "none";
        if (playFlow3DLabel) playFlow3DLabel.textContent = "Play Flow";
        if (playFlow3DBtn) playFlow3DBtn.classList.remove("active");
    }

    if (playFlow3DBtn) {
        playFlow3DBtn.addEventListener("click", () => {
            if (flowGraphState.isPlaying) {
                pause3DFlow();
            } else {
                play3DFlow();
            }
        });
    }

    if (stepForward3DBtn) {
        stepForward3DBtn.addEventListener("click", () => {
            pause3DFlow();
            const steps = flowGraphState.steps;
            if (steps && steps.length) {
                flowGraphState.currentStep = (flowGraphState.currentStep + 1) % steps.length;
                updateFlowPlayerUI(flowGraphState.currentStep);
            }
        });
    }

    if (stepBack3DBtn) {
        stepBack3DBtn.addEventListener("click", () => {
            pause3DFlow();
            const steps = flowGraphState.steps;
            if (steps && steps.length) {
                flowGraphState.currentStep = (flowGraphState.currentStep - 1 + steps.length) % steps.length;
                updateFlowPlayerUI(flowGraphState.currentStep);
            }
        });
    }

    if (restart3DFlowBtn) {
        restart3DFlowBtn.addEventListener("click", () => {
            pause3DFlow();
            flowGraphState.currentStep = 0;
            updateFlowPlayerUI(0);
        });
    }

    if (flow3DSpeedSelect) {
        flow3DSpeedSelect.addEventListener("change", (e) => {
            flowGraphState.speedMs = parseInt(e.target.value, 10) || 700;
            if (flowGraphState.isPlaying) {
                pause3DFlow();
                play3DFlow();
            }
        });
    }

    function showNodeHud(node) {
        if (!node || !threedNodeHud) return;
        if (hudNodeCategory) {
            hudNodeCategory.textContent = (node.category || "NODE").toUpperCase();
            hudNodeCategory.className = `badge-sev badge-${(node.category === 'function' ? 'critical' : node.category === 'loop' ? 'high' : 'medium')}`;
        }
        if (hudNodeLabel) hudNodeLabel.textContent = node.label || "Code Component";
        if (hudNodeDesc) hudNodeDesc.textContent = node.description || "Active program execution entity.";
        if (hudNodeSnippet) hudNodeSnippet.textContent = node.snippet || node.label;
        if (hudNodeLine) hudNodeLine.textContent = node.line || 1;
        if (hudNodeComplexity) hudNodeComplexity.textContent = node.complexity || "O(1)";

        if (hudJumpBtn) {
            hudJumpBtn.onclick = () => {
                focusLine(node.line || 1);
            };
        }

        threedNodeHud.style.display = "block";
    }

    if (closeNodeHudBtn) {
        closeNodeHudBtn.addEventListener("click", () => {
            if (threedNodeHud) threedNodeHud.style.display = "none";
        });
    }

    function clearReviewResults() {
        state.reviewData = null;
        state.issues = [];
        issueCountPill.textContent = "0";
        scoreSummaryPill.textContent = "--";
        summaryStatusTitle.textContent = "Awaiting Code Submission";
        summaryStatusDesc.textContent = "Click 'Review Code' above to trigger static AST analysis and bug hunting.";
        issuesListContainer.innerHTML = `
            <div class="empty-state">
                <div class="empty-icon">🔍</div>
                <h3>No Review Run Yet</h3>
                <p>Type or paste code into the editor and click <strong>Review Code</strong>.</p>
            </div>
        `;
        scoreNumberVal.textContent = "--";
        scoreRingCircle.style.strokeDashoffset = "314";
        scoreVerdict.textContent = "Awaiting review...";
        if (threedNodeHud) threedNodeHud.style.display = "none";
        pause3DFlow();
    }

    function escapeHtml(text) {
        if (!text) return "";
        return String(text)
            .replace(/&/g, "&amp;")
            .replace(/</g, "&lt;")
            .replace(/>/g, "&gt;")
            .replace(/"/g, "&quot;")
            .replace(/'/g, "&#039;");
    }

    // ==========================================================================
    // Automatic Startup Boot: Load initial C++ preset and trigger review
    // ==========================================================================
    const initialPresetKey = samplePreset.value || "cpp_two_sum_bug";
    loadPreset(initialPresetKey);
    setTimeout(() => {
        performReview();
    }, 150);
});

