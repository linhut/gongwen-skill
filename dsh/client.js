// 公文全流程处理工具 DSH client — 设置平级菜单「文档样式配置」（gongwen-skill）
// (c) 2026 Jose AI (https://www.linhut.cn)
// https://github.com/linhut/gongwen-skill
// Licensed under the MIT License. See the LICENSE file for details.
//
// 官方依据：DeepSeek Harness Bluebook Developer Guide · Client UI & Slots
//   - 只写纯 JavaScript：无 TS/JSX/import/require，React 用 React.createElement
//   - 设置侧边栏平级菜单：注册 settings.section（id=gongwen-styles, order=20,
//     label=文档样式配置），取代原 settings.plugin.item 插件配置卡片
//   - 通过 ctx.settingsScope.bind({ namespace }) 读写官方 settings 命名空间（revision 设栅）
//   - 模板管理/上传经 host webServer 路由（/plugins/gongwen/api/*）
//   - 样式使用 --dsw-alias-* 语义 token，不写死颜色
//   - 打包格式 = loader 的 lazy-CJS factory 产物（window.__ModuleLoader__.load）

window.__ModuleLoader__.load({
  id: "gongwen-skill",
  factory: (require) => {
    var module = { exports: {} };
    var exports = module.exports;
    Object.defineProperty(exports, Symbol.toStringTag, { value: "Module" });

    var react = require("react");
    var h = react.createElement;
    var useState = react.useState;
    var useEffect = react.useEffect;
    var useCallback = react.useCallback;
    var useRef = react.useRef;

    // 与 Host 侧 ctx.settings.register 配对的命名空间
    var NS = "gongwen-skill";

    // 25 种公文类型（与 rules/official/*.yaml 及 list-types 输出一致）
    // 用于「默认公文类型」下拉；value 为英文 id（配置存储值，与 CLI --doc-type 兼容），
    // label 为中文名（取自各 rules/official/<id>.yaml 的 template_name）。
    // 若 settings 中已有值不在列表内，会追加显示该值。
    var DOC_TYPES = [
      { value: "announcement", label: "通告" },
      { value: "bill", label: "议案" },
      { value: "bulletin", label: "通报" },
      { value: "command", label: "命令（令）" },
      { value: "communique", label: "公报" },
      { value: "decision", label: "决定" },
      { value: "host_speech", label: "主持词" },
      { value: "instruction", label: "指示" },
      { value: "letter", label: "函" },
      { value: "meeting", label: "会议纪要" },
      { value: "minutes", label: "纪要" },
      { value: "news", label: "新闻稿/简报" },
      { value: "notice", label: "通知" },
      { value: "notice_public", label: "公告" },
      { value: "opinion", label: "意见" },
      { value: "regulation", label: "制度" },
      { value: "reply", label: "批复" },
      { value: "report", label: "报告" },
      { value: "request", label: "请示" },
      { value: "resolution", label: "决议" },
      { value: "speech", label: "讲话稿" },
      { value: "summary", label: "总结" },
      { value: "table_sign", label: "座签" },
      { value: "technical_proposal", label: "技术方案" },
      { value: "work_plan", label: "工作方案" },
    ];

    // 扁平字段表：path（嵌套数组）、label、placeholder、type（text|checkbox|select）
    // 与 dsh/index.js 的 settings schema 保持一一对应
    var FIELDS = [
      { path: ["default_doc_type"], label: "默认公文类型", placeholder: "notice", type: "select" },

      { path: ["page_setup", "margins", "top"], label: "上边距", placeholder: "2.8cm", type: "text" },
      { path: ["page_setup", "margins", "bottom"], label: "下边距", placeholder: "2.8cm", type: "text" },
      { path: ["page_setup", "margins", "left"], label: "左边距", placeholder: "2.7cm", type: "text" },
      { path: ["page_setup", "margins", "right"], label: "右边距", placeholder: "2.7cm", type: "text" },
      { path: ["page_setup", "header_distance"], label: "页眉距", placeholder: "1.5cm", type: "text" },
      { path: ["page_setup", "footer_distance"], label: "页脚距", placeholder: "2.3cm", type: "text" },

      { path: ["body", "font"], label: "正文·字体", placeholder: "仿宋_GB2312", type: "text" },
      { path: ["body", "font_fallback"], label: "正文·字体回退", placeholder: "FangSong", type: "text" },
      { path: ["body", "size"], label: "正文·字号", placeholder: "16pt", type: "text" },
      { path: ["body", "line_spacing"], label: "正文·行距", placeholder: "33pt", type: "text" },
      { path: ["body", "first_line_indent"], label: "正文·首行缩进", placeholder: "2em", type: "text" },
      { path: ["body", "align"], label: "正文·对齐", placeholder: "justify", type: "text" },

      { path: ["doc_title", "font"], label: "标题·字体", placeholder: "方正小标宋简体", type: "text" },
      { path: ["doc_title", "font_fallback"], label: "标题·字体回退", placeholder: "SimSun", type: "text" },
      { path: ["doc_title", "size"], label: "标题·字号", placeholder: "22pt", type: "text" },
      { path: ["doc_title", "align"], label: "标题·对齐", placeholder: "center", type: "text" },
      { path: ["doc_title", "bold"], label: "标题·加粗", type: "checkbox" },
      { path: ["doc_title", "line_spacing"], label: "标题·行距", placeholder: "33pt", type: "text" },

      { path: ["heading_1", "font"], label: "一级标题·字体", placeholder: "黑体", type: "text" },
      { path: ["heading_1", "font_fallback"], label: "一级标题·字体回退", placeholder: "SimHei", type: "text" },
      { path: ["heading_1", "size"], label: "一级标题·字号", placeholder: "16pt", type: "text" },
      { path: ["heading_1", "line_spacing"], label: "一级标题·行距", placeholder: "33pt", type: "text" },
      { path: ["heading_1", "first_line_indent"], label: "一级标题·首行缩进", placeholder: "2em", type: "text" },

      { path: ["heading_2", "font"], label: "二级标题·字体", placeholder: "楷体_GB2312", type: "text" },
      { path: ["heading_2", "font_fallback"], label: "二级标题·字体回退", placeholder: "KaiTi", type: "text" },
      { path: ["heading_2", "size"], label: "二级标题·字号", placeholder: "16pt", type: "text" },
      { path: ["heading_2", "line_spacing"], label: "二级标题·行距", placeholder: "33pt", type: "text" },
      { path: ["heading_2", "first_line_indent"], label: "二级标题·首行缩进", placeholder: "2em", type: "text" },

      { path: ["heading_3", "font"], label: "三级标题·字体", placeholder: "仿宋_GB2312", type: "text" },
      { path: ["heading_3", "font_fallback"], label: "三级标题·字体回退", placeholder: "FangSong", type: "text" },
      { path: ["heading_3", "size"], label: "三级标题·字号", placeholder: "16pt", type: "text" },
      { path: ["heading_3", "bold"], label: "三级标题·加粗", type: "checkbox" },
      { path: ["heading_3", "line_spacing"], label: "三级标题·行距", placeholder: "33pt", type: "text" },
      { path: ["heading_3", "first_line_indent"], label: "三级标题·首行缩进", placeholder: "2em", type: "text" },

      { path: ["signature", "font"], label: "署名·字体", placeholder: "仿宋_GB2312", type: "text" },
      { path: ["signature", "font_fallback"], label: "署名·字体回退", placeholder: "FangSong", type: "text" },
      { path: ["signature", "size"], label: "署名·字号", placeholder: "18pt", type: "text" },
      { path: ["signature", "align"], label: "署名·对齐", placeholder: "center", type: "text" },
    ];

    // 从嵌套 value 中取路径值
    function getPath(obj, path) {
      var cur = obj;
      for (var i = 0; i < path.length; i++) {
        if (cur === null || cur === undefined || typeof cur !== "object") return undefined;
        cur = cur[path[i]];
      }
      return cur;
    }

    // 深拷贝（JSON 安全数据）
    function clone(v) {
      return JSON.parse(JSON.stringify(v === undefined ? null : v));
    }

    // ---- 配置 controller：暂存编辑 → scope.mutate 一次性提交 ----
    function makeCardController(scope) {
      var snapshot = { status: "loading", value: null, writable: false, base: null, user: null };
      var staged = {}; // pathKey -> { value, overridden }
      var saving = false;
      var failed = false;
      var message = "";
      var listeners = [];

      function emit() {
        for (var i = 0; i < listeners.length; i++) {
          try { listeners[i](); } catch (_) {}
        }
      }

      function refresh() {
        snapshot = scope.getSnapshot();
        emit();
      }

      var unsubscribe = null;
      try {
        unsubscribe = scope.subscribe(refresh);
      } catch (_) {}
      refresh();

      // pathKey: "page_setup.margins.top"
      function pathKey(path) { return path.join("."); }

      function fieldValue(path) {
        var k = pathKey(path);
        if (Object.prototype.hasOwnProperty.call(staged, k)) return staged[k].value;
        return getPath(snapshot.value, path);
      }

      function fieldOverridden(path) {
        var k = pathKey(path);
        if (Object.prototype.hasOwnProperty.call(staged, k)) return staged[k].overridden;
        // user 层中出现该字段即视为用户覆盖（官方语义：presence，不是值比较）
        return getPath(snapshot.user, path) !== undefined;
      }

      function setField(path, value) {
        staged[pathKey(path)] = { value: value, overridden: true };
        failed = false;
        message = "";
        emit();
      }

      function clearField(path) {
        var k = pathKey(path);
        if (Object.prototype.hasOwnProperty.call(staged, k)) delete staged[k];
        // 无 staged 时直接 unset 立即生效由 save 统一处理；这里仅标记需要清除
        staged[k] = { value: undefined, overridden: true, clear: true };
        failed = false;
        message = "";
        emit();
      }

      function resetAll() {
        staged = {};
        for (var i = 0; i < FIELDS.length; i++) {
          var f = FIELDS[i];
          staged[pathKey(f.path)] = { value: getPath(snapshot.base, f.path), overridden: true, clear: true };
        }
        failed = false;
        message = "已恢复默认值（需点击保存生效）";
        emit();
      }

      function save() {
        if (saving) return;
        var ops = [];
        for (var k in staged) {
          if (!Object.prototype.hasOwnProperty.call(staged, k)) continue;
          var edit = staged[k];
          var path = k.split(".");
          if (edit.clear) {
            ops.push({ op: "unset", path: path });
          } else {
            ops.push({ op: "set", path: path, value: edit.value });
          }
        }
        if (ops.length === 0) {
          message = "没有待保存的修改";
          emit();
          return;
        }
        saving = true;
        failed = false;
        message = "";
        emit();
        scope.mutate(ops)
          .then(function () {
            saving = false;
            staged = {};
            message = "✅ 配置已保存（已同步到 ~/.gongwen-skill/dsh-config.json）";
            emit();
          })
          .catch(function (e) {
            saving = false;
            failed = true;
            message = "保存失败：" + (e && e.message ? e.message : "未知错误");
            emit();
          });
      }

      return {
        getSnapshot: function () {
          return {
            status: snapshot.status,
            writable: snapshot.writable,
            saving: saving,
            failed: failed,
            message: message,
          };
        },
        fieldValue: fieldValue,
        fieldOverridden: fieldOverridden,
        setField: setField,
        clearField: clearField,
        resetAll: resetAll,
        save: save,
        subscribe: function (cb) {
          listeners.push(cb);
          return function () {
            listeners = listeners.filter(function (l) { return l !== cb; });
          };
        },
        dispose: function () {
          if (unsubscribe) { try { unsubscribe(); } catch (_) {} }
          listeners = [];
        },
      };
    }

    // ---- 纯展示组件（React.createElement，--dsw-alias-* token）----
    function FieldRow(props) {
      var f = props.field;
      var value = props.value;
      var overridden = props.overridden;
      var onChange = props.onChange;
      var disabled = props.disabled;

      if (f.type === "checkbox") {
        return h("label", {
          style: {
            display: "flex", alignItems: "center", gap: "8px",
            padding: "6px 0", fontSize: "13px", lineHeight: "1.5",
            color: "var(--dsw-alias-label-primary)",
          },
        },
          h("input", {
            type: "checkbox",
            checked: !!value,
            disabled: disabled,
            onChange: function (e) { onChange(e.target.checked); },
            style: { accentColor: "var(--dsw-alias-brand-primary)" },
          }),
          h("span", null, f.label + (overridden ? "（已自定义）" : "")),
        );
      }

      if (f.type === "select") {
        var cur = value === undefined || value === null ? "" : String(value);
        var opts = DOC_TYPES.slice();
        if (cur && !opts.some(function (o) { return o.value === cur; })) opts.unshift({ value: cur, label: cur });
        return h("label", {
          style: {
            display: "flex", alignItems: "center", gap: "10px",
            padding: "5px 0", fontSize: "13px", lineHeight: "1.5",
            color: "var(--dsw-alias-label-primary)",
          },
        },
          h("span", {
            style: {
              minWidth: "140px", flexShrink: 0,
              color: "var(--dsw-alias-label-secondary)",
            },
          }, f.label),
          h("select", {
            value: cur,
            disabled: disabled,
            onChange: function (e) { onChange(e.target.value); },
            style: {
              flex: 1, minWidth: 0, height: "32px", padding: "0 10px",
              fontSize: "13px", lineHeight: "1.5",
              border: "1px solid var(--dsw-alias-border-l4)",
              borderRadius: "6px",
              background: "var(--dsw-alias-bg-layer-3)",
              color: "var(--dsw-alias-label-primary)",
            },
          },
            opts.map(function (o) {
              return h("option", { key: o.value, value: o.value }, o.label);
            })
          ),
          h("span", {
            style: {
              flexShrink: 0, fontSize: "11px",
              color: overridden
                ? "var(--dsw-alias-label-secondary)"
                : "var(--dsw-alias-label-tertiary)",
            },
          }, overridden ? "已自定义" : "默认"),
        );
      }

      return h("label", {
        style: {
          display: "flex", alignItems: "center", gap: "10px",
          padding: "5px 0", fontSize: "13px", lineHeight: "1.5",
          color: "var(--dsw-alias-label-primary)",
        },
      },
        h("span", {
          style: {
            minWidth: "140px", flexShrink: 0,
            color: "var(--dsw-alias-label-secondary)",
          },
        }, f.label),
        h("input", {
          type: "text",
          value: value === undefined || value === null ? "" : String(value),
          placeholder: f.placeholder,
          disabled: disabled,
          onChange: function (e) { onChange(e.target.value); },
          style: {
            flex: 1, minWidth: 0, height: "30px", padding: "0 10px",
            fontSize: "13px", lineHeight: "1.5",
            border: "1px solid var(--dsw-alias-border-l4)",
            borderRadius: "6px",
            background: "var(--dsw-alias-bg-layer-3)",
            color: "var(--dsw-alias-label-primary)",
          },
        }),
        h("span", {
          style: {
            flexShrink: 0, fontSize: "11px",
            color: overridden
              ? "var(--dsw-alias-label-secondary)"
              : "var(--dsw-alias-label-tertiary)",
          },
        }, overridden ? "已自定义" : "默认"),
      );
    }

    function Section(props) {
      return h("fieldset", {
        style: {
          border: "1px solid var(--dsw-alias-border-l2)",
          borderRadius: "10px", padding: "12px 14px", margin: "0 0 14px",
        },
      },
        h("legend", {
          style: {
            fontSize: "13px", fontWeight: 600, padding: "0 8px",
            color: "var(--dsw-alias-label-primary)",
          },
        }, props.title),
        props.children,
      );
    }

    // ---- 模板样式管理：列表 + YAML 文本编辑 ----
    function TemplateManager(props) {
      var refreshToken = props.refreshToken;
      var [templates, setTemplates] = useState(null); // null = 加载中
      var [editing, setEditing] = useState(null);     // {name, content}
      var [busy, setBusy] = useState(false);
      var [message, setMessage] = useState("");

      function loadTemplates() {
        fetch("/plugins/gongwen/api/templates")
          .then(function (r) { return r.json(); })
          .then(function (d) {
            if (d && d.ok) {
              setTemplates(d.templates || []);
            } else {
              setTemplates([]);
              setMessage("模板列表加载失败：" + ((d && d.error) || "unknown"));
            }
          })
          .catch(function (e) { setTemplates([]); setMessage("模板列表加载失败：" + e.message); });
      }

      useEffect(function () { loadTemplates(); }, [refreshToken]);

      function openEdit(name) {
        setBusy(true);
        setMessage("");
        fetch("/plugins/gongwen/api/template?name=" + encodeURIComponent(name))
          .then(function (r) { return r.json(); })
          .then(function (d) {
            if (d && d.ok) {
              setEditing({ name: d.name, content: d.content });
            } else {
              setMessage("读取模板失败：" + ((d && d.error) || "unknown"));
            }
          })
          .catch(function (e) { setMessage("读取模板失败：" + e.message); })
          .then(function () { setBusy(false); });
      }

      function saveEdit() {
        if (!editing) return;
        setBusy(true);
        setMessage("");
        fetch("/plugins/gongwen/api/template-save?name=" + encodeURIComponent(editing.name), {
          method: "PUT",
          headers: { "Content-Type": "text/plain; charset=utf-8" },
          body: editing.content,
        })
          .then(function (r) { return r.json(); })
          .then(function (d) {
            if (d && d.ok) {
              setMessage("✅ " + (d.message || "模板已保存"));
              setEditing(null);
              loadTemplates();
            } else {
              setMessage("保存失败：" + ((d && d.error) || "unknown"));
            }
          })
          .catch(function (e) { setMessage("保存失败：" + e.message); })
          .then(function () { setBusy(false); });
      }

      function closeEdit() {
        setEditing(null);
        setMessage("");
      }

      var buttonStyle = {
        padding: "4px 14px", fontSize: "13px",
        border: "1px solid var(--dsw-alias-border-l4)",
        borderRadius: "6px",
        background: "var(--dsw-alias-bg-layer-2, #f5f5f5)",
        color: "var(--dsw-alias-label-primary)",
        cursor: busy ? "not-allowed" : "pointer",
        opacity: busy ? 0.6 : 1,
      };

      if (editing) {
        return h("div", null,
          h("div", { style: { display: "flex", alignItems: "center", gap: "10px", marginBottom: "8px" } },
            h("span", { style: { fontSize: "13px", fontWeight: 600, color: "var(--dsw-alias-label-primary)" } },
              "编辑模板：" + editing.name + ".yaml"),
            h("span", { style: { flex: 1 } }),
            h("button", { style: buttonStyle, disabled: busy, onClick: saveEdit }, busy ? "保存中..." : "💾 保存"),
            h("button", { style: buttonStyle, disabled: busy, onClick: closeEdit }, "取消"),
          ),
          message && h("div", { style: { padding: "6px 10px", margin: "0 0 8px", borderRadius: "6px", fontSize: "12px", background: "rgba(40,120,60,.12)", color: "var(--dsw-alias-label-success, #2e7d32)" } }, message),
          h("textarea", {
            value: editing.content,
            disabled: busy,
            onChange: function (e) { setEditing({ name: editing.name, content: e.target.value }); },
            spellCheck: false,
            style: {
              width: "100%", minHeight: "260px", boxSizing: "border-box",
              padding: "10px", fontFamily: "var(--ds-font-family-code, ui-monospace, monospace)",
              fontSize: "12px", lineHeight: "1.6",
              border: "1px solid var(--dsw-alias-border-l4)",
              borderRadius: "8px",
              background: "var(--dsw-alias-bg-layer-3)",
              color: "var(--dsw-alias-label-primary)",
              whiteSpace: "pre", resize: "vertical",
            },
          }),
          h("div", { style: { marginTop: "6px", fontSize: "11px", color: "var(--dsw-alias-label-tertiary)" } },
            "提示：首行 template_name 必须与文件名一致；保存后 optimize -t " + editing.name + " 立即生效"),
        );
      }

      if (templates === null) {
        return h("div", { style: { padding: "8px 0", color: "var(--dsw-alias-label-tertiary)", fontSize: "13px" } }, "加载模板列表…");
      }

      if (templates.length === 0) {
        return h("div", null,
          message && h("div", { style: { padding: "6px 10px", margin: "0 0 8px", borderRadius: "6px", fontSize: "12px", background: "rgba(200,40,40,.12)", color: "var(--dsw-alias-label-error)" } }, message),
          h("div", { style: { padding: "8px 0", color: "var(--dsw-alias-label-tertiary)", fontSize: "13px" } },
            "暂无自定义样式模板——请在下方「通过文档新增样式模板」上传一份标准 .docx 学习生成。"),
        );
      }

      return h("div", null,
        message && h("div", { style: { padding: "6px 10px", margin: "0 0 8px", borderRadius: "6px", fontSize: "12px", background: "rgba(200,40,40,.12)", color: "var(--dsw-alias-label-error)" } }, message),
        h("div", { style: { display: "flex", flexWrap: "wrap", gap: "8px" } },
          templates.map(function (name) {
            return h("div", {
              key: name,
              style: {
                display: "flex", alignItems: "center", gap: "8px",
                padding: "6px 10px", fontSize: "13px",
                border: "1px solid var(--dsw-alias-border-l2)",
                borderRadius: "8px",
                background: "var(--dsw-alias-bg-layer-2, #f5f5f5)",
                color: "var(--dsw-alias-label-primary)",
              },
            },
              h("span", null, name),
              h("span", { style: { fontSize: "11px", color: "var(--dsw-alias-label-tertiary)" } }, ".yaml"),
              h("button", {
                style: {
                  padding: "2px 10px", fontSize: "12px",
                  border: "1px solid var(--dsw-alias-border-l4)",
                  borderRadius: "6px",
                  background: "var(--dsw-alias-bg-layer-3)",
                  color: "var(--dsw-alias-label-primary)",
                  cursor: "pointer",
                },
                onClick: function () { openEdit(name); },
              }, "✏️ 编辑"),
            );
          })
        ),
        h("div", { style: { marginTop: "8px", fontSize: "11px", color: "var(--dsw-alias-label-tertiary)" } },
          "模板存储于 ~/.gongwen-skill/user_rules/（仓库之外，git 更新不丢失）"),
      );
    }

    // ---- 通过文档新增样式模板：上传 .docx → host → style-learn ----
    function StyleLearnUploader(props) {
      var fileRef = useRef(null);
      var [fileName, setFileName] = useState("");
      var [templateName, setTemplateName] = useState("");
      var [busy, setBusy] = useState(false);
      var [message, setMessage] = useState("");
      var [ok, setOk] = useState(false);

      function handleFile(e) {
        var f = e.target.files && e.target.files[0];
        if (!f) return;
        setOk(false);
        setMessage("");
        setFileName(f.name);
        // 模板名默认取文件名（去 .docx、非法字符转 _），用户可改
        var autoName = f.name.replace(/\.docx$/i, "").replace(/[^a-zA-Z0-9_\-\u4e00-\u9fff]/g, "_").slice(0, 60) || "自定义";
        setTemplateName(autoName);
        var reader = new FileReader();
        reader.onload = function () {
          setBusy(true);
          setMessage("正在学习文档样式…");
          fetch("/plugins/gongwen/api/style-learn", {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ filename: f.name, name: autoName, data: String(reader.result) }),
          })
            .then(function (r) { return r.json(); })
            .then(function (d) {
              if (d && d.ok) {
                setOk(true);
                setMessage("✅ 模板「" + d.template_name + "」已生成，可在模板管理区查看/编辑，或用 optimize -t " + d.template_name + " 套用");
                if (props.onDone) props.onDone();
              } else {
                var detail = (d && d.error) || "学习失败";
                if (d && d.output) detail += " " + d.output;
                if (d && d.stderr) detail += " " + d.stderr;
                setMessage("❌ " + detail);
              }
            })
            .catch(function (err) { setMessage("❌ 上传失败：" + err.message); })
            .then(function () { setBusy(false); });
        };
        reader.readAsDataURL(f);
      }

      var inputStyle = {
        flex: 1, minWidth: 0, height: "30px", padding: "0 10px",
        fontSize: "13px", lineHeight: "1.5",
        border: "1px solid var(--dsw-alias-border-l4)",
        borderRadius: "6px",
        background: "var(--dsw-alias-bg-layer-3)",
        color: "var(--dsw-alias-label-primary)",
      };

      return h("div", null,
        message && h("div", {
          style: {
            padding: "6px 10px", margin: "0 0 8px", borderRadius: "6px", fontSize: "12px",
            background: ok ? "rgba(40,120,60,.12)" : "rgba(200,40,40,.12)",
            color: ok ? "var(--dsw-alias-label-success, #2e7d32)" : "var(--dsw-alias-label-error)",
          },
        }, message),

        h("div", { style: { display: "flex", alignItems: "center", gap: "10px", flexWrap: "wrap" } },
          h("input", {
            ref: fileRef,
            type: "file",
            accept: ".docx,application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            disabled: busy,
            onChange: handleFile,
            style: { fontSize: "13px", color: "var(--dsw-alias-label-primary)" },
          }),
          h("span", { style: { fontSize: "12px", color: "var(--dsw-alias-label-tertiary)" } }, "→"),
          h("label", { style: { display: "flex", alignItems: "center", gap: "8px", fontSize: "13px", color: "var(--dsw-alias-label-primary)" } },
            "模板名：",
            h("input", {
              type: "text",
              value: templateName,
              disabled: busy,
              placeholder: "如：单位红头规范",
              onChange: function (e) { setTemplateName(e.target.value); },
              style: Object.assign({}, inputStyle, { width: "200px", flex: "none" }),
            }),
          ),
          busy && h("span", { style: { fontSize: "13px", color: "var(--dsw-alias-label-tertiary)" } }, "处理中…"),
        ),

        h("div", { style: { marginTop: "8px", fontSize: "11px", color: "var(--dsw-alias-label-tertiary)" } },
          "选择一份标准公文 .docx（如单位定稿红头文件），系统将自动学习其字体/字号/字间距/行距/缩进/页边距并生成为命名模板；选中文件即开始学习，无需额外按钮。" + (fileName ? " 已选：" + fileName : "")),
      );
    }

    // ---- 设置页「文档样式配置」主组件（settings.section 内容）----
    function GongwenStylesSection(props) {
      var face = props.face;
      var [, force] = useState(0);
      var [tmplRefresh, setTmplRefresh] = useState(0);

      useEffect(function () {
        return face.subscribe(function () { force(function (n) { return n + 1; }); });
      }, [face]);

      var meta = face.getSnapshot();
      var unavailable = meta.status !== "ready";
      var disabled = !meta.writable || meta.saving || unavailable;

      function renderGroup(groupLabel, fields) {
        return h(Section, { title: groupLabel },
          fields.map(function (f) {
            return h(FieldRow, {
              key: f.path.join("."),
              field: f,
              value: face.fieldValue(f.path),
              overridden: face.fieldOverridden(f.path),
              onChange: function (v) { face.setField(f.path, v); },
              disabled: disabled,
            });
          })
        );
      }

      return h("div", {
        style: {
          padding: "16px 4px", maxWidth: "760px",
          fontSize: "14px", lineHeight: "1.6",
          color: "var(--dsw-alias-label-primary)",
        },
      },
        meta.message && h("div", {
          style: {
            padding: "8px 12px", marginBottom: "12px",
            borderRadius: "8px", fontSize: "13px", lineHeight: "1.5",
            background: meta.failed ? "var(--dsw-alias-bg-danger, rgba(200,40,40,.12))" : "var(--dsw-alias-bg-success, rgba(40,120,60,.12))",
            color: meta.failed ? "var(--dsw-alias-label-error)" : "var(--dsw-alias-label-success, #2e7d32)",
          },
        }, meta.message),

        unavailable && h("div", {
          style: { padding: "12px 0", color: "var(--dsw-alias-label-tertiary)" },
        }, "设置服务不可用（当前部署未挂载 settings provider），排版参数区只读。"),

        renderGroup("基础设置", FIELDS.slice(0, 1)),
        renderGroup("页面设置", FIELDS.slice(1, 7)),
        renderGroup("正文格式", FIELDS.slice(7, 13)),
        renderGroup("公文标题", FIELDS.slice(13, 19)),
        renderGroup("一级标题", FIELDS.slice(19, 24)),
        renderGroup("二级标题", FIELDS.slice(24, 29)),
        renderGroup("三级标题", FIELDS.slice(29, 35)),
        renderGroup("署名格式", FIELDS.slice(35, 39)),

        h("div", { style: { display: "flex", gap: "10px", marginTop: "16px", alignItems: "center" } },
          h("button", {
            onClick: face.save,
            disabled: disabled,
            style: {
              padding: "6px 20px", fontSize: "14px", fontWeight: 600,
              border: "1px solid var(--dsw-alias-border-l4)",
              borderRadius: "8px",
              background: "var(--dsw-alias-brand-primary)",
              color: "#fff",
              cursor: disabled ? "not-allowed" : "pointer",
              opacity: disabled ? 0.6 : 1,
            },
          }, meta.saving ? "保存中..." : "💾 保存配置"),
          h("button", {
            onClick: face.resetAll,
            disabled: disabled,
            style: {
              padding: "6px 20px", fontSize: "14px",
              border: "1px solid var(--dsw-alias-border-l4)",
              borderRadius: "8px",
              background: "var(--dsw-alias-bg-layer-2, #f5f5f5)",
              color: "var(--dsw-alias-label-primary)",
              cursor: disabled ? "not-allowed" : "pointer",
            },
          }, "↩ 恢复默认"),
          h("span", {
            style: {
              fontSize: "12px", flex: 1, textAlign: "right",
              color: "var(--dsw-alias-label-tertiary)",
            },
          }, "同步文件: ~/.gongwen-skill/dsh-config.json"),
        ),

        h(Section, { title: "模板样式管理" },
          h(TemplateManager, { refreshToken: tmplRefresh })
        ),

        h(Section, { title: "通过文档新增样式模板" },
          h(StyleLearnUploader, {
            onDone: function () { setTmplRefresh(function (n) { return n + 1; }); },
          })
        ),
      );
    }

    // 导出 apply + inject（官方 Client UI & Slots 注册方式：
    // settings.section 在设置侧边栏出现独立平级菜单）
    exports.apply = function (ctx) {
      var slots = ctx.get("slots");
      var settingsScope = ctx.get("settingsScope");
      if (!slots || !settingsScope) return;

      var scope = settingsScope.bind({ namespace: NS });
      var controller = makeCardController(scope);

      // 注册设置侧边栏平级菜单「文档样式配置」
      slots.inject("settings.section", function () {
        return slots.register({
          name: "settings.section",
          id: "gongwen-styles",
          order: 20,
          label: "文档样式配置",
          locale: "settings",
          inject: function () {
            return { face: controller };
          },
        }, GongwenStylesSection);
      });

      // 插件卸载时释放订阅
      ctx.effect(function () {
        return function () { controller.dispose(); };
      }, "gongwen-skill: client controller cleanup");
    };
    exports.inject = ["slots", "settingsScope"];

    return module.exports;
  },
});