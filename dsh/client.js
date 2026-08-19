// 公文全流程处理工具 DSH client — 可视化配置面板（gongwen-skill，不做皮肤，仅设置面板）
// (c) 2026 Jose AI (https://www.linhut.cn)
// https://github.com/linhut/gongwen-skill
// Licensed under the MIT License. See the LICENSE file for details.
//
// 在 DSH Web GUI 系统设置 → 插件配置 中渲染公文排版参数编辑界面。
// 通过 /plugins/gongwen-skill/api/config (GET/POST) 与宿主端通信。

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

    var API_BASE = "/plugins/gongwen-skill/api";

    // 获取当前配置
    function fetchConfig() {
      return fetch(API_BASE + "/config").then(function (r) { return r.json(); });
    }

    // 保存配置
    function saveConfig(config) {
      return fetch(API_BASE + "/config", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(config),
      }).then(function (r) { return r.json(); });
    }

    // 获取默认配置
    function fetchDefaults() {
      return fetch(API_BASE + "/defaults").then(function (r) { return r.json(); });
    }

    // 输入框组件
    function ConfigInput(_a) {
      var label = _a.label, value = _a.value, onChange = _a.onChange, placeholder = _a.placeholder;
      return h("label", { style: { display: "flex", alignItems: "center", gap: "8px", marginBottom: "6px" } },
        h("span", { style: { minWidth: "100px", fontSize: "13px", color: "var(--ds-text-secondary, #666)" } }, label),
        h("input", {
          type: "text",
          value: value || "",
          placeholder: placeholder,
          onChange: function (e) { onChange(e.target.value); },
          style: {
            flex: 1, padding: "4px 8px", fontSize: "13px",
            border: "1px solid var(--ds-border, #ddd)", borderRadius: "4px",
            background: "var(--ds-input-bg, #fff)", color: "var(--ds-text, #333)",
          },
        })
      );
    }

    // 分组标题
    function Section(_a) {
      var title = _a.title, children = _a.children;
      return h("fieldset", {
        style: { border: "1px solid var(--ds-border, #ddd)", borderRadius: "6px", padding: "12px", marginBottom: "12px" },
      },
        h("legend", { style: { fontSize: "13px", fontWeight: 600, padding: "0 8px", color: "var(--ds-text, #333)" } }, title),
        children
      );
    }

    // 主配置面板
    function GongwenConfigPanel() {
      var config = useState(null)[0], setConfig = useState(null)[1];
      var defaults = useState(null)[0], setDefaults = useState(null)[1];
      var saving = useState(false)[0], setSaving = useState(false)[1];
      var message = useState("")[0], setMessage = useState("")[1];
      var error = useState("")[0], setError = useState("")[1];

      useEffect(function () {
        fetchConfig().then(function (data) {
          if (data.ok) setConfig(data.config);
        }).catch(function (e) { setError("加载配置失败: " + e.message); });
        fetchDefaults().then(function (data) {
          if (data.ok) setDefaults(data.defaults);
        }).catch(function () {});
      }, []);

      var updateField = useCallback(function (path, value) {
        var keys = path.split(".");
        var next = JSON.parse(JSON.stringify(config || {}));
        var cur = next;
        for (var i = 0; i < keys.length - 1; i++) {
          if (!cur[keys[i]]) cur[keys[i]] = {};
          cur = cur[keys[i]];
        }
        cur[keys[keys.length - 1]] = value;
        setConfig(next);
      }, [config]);

      var handleSave = useCallback(function () {
        setSaving(true);
        setMessage("");
        setError("");
        saveConfig(config).then(function (data) {
          setSaving(false);
          if (data.ok) {
            setMessage("✅ 配置已保存");
            setTimeout(function () { setMessage(""); }, 3000);
          } else {
            setError("保存失败: " + (data.error || "未知错误"));
          }
        }).catch(function (e) {
          setSaving(false);
          setError("保存失败: " + e.message);
        });
      }, [config]);

      var handleReset = useCallback(function () {
        if (!defaults) return;
        var next = {};
        for (var k in defaults) {
          if (!k.startsWith("_")) next[k] = defaults[k];
        }
        setConfig(next);
        setMessage("已恢复默认值（需点击保存生效）");
        setTimeout(function () { setMessage(""); }, 3000);
      }, [defaults]);

      if (!config) {
        return h("div", { style: { padding: "20px", textAlign: "center", color: "var(--ds-text-secondary, #999)" } }, "加载配置中...");
      }

      return h("div", { style: { padding: "16px", maxWidth: "700px", fontSize: "14px" } },
        // 消息条
        message && h("div", { style: { padding: "8px 12px", marginBottom: "12px", background: "#e8f5e9", borderRadius: "4px", color: "#2e7d32", fontSize: "13px" } }, message),
        error && h("div", { style: { padding: "8px 12px", marginBottom: "12px", background: "#ffebee", borderRadius: "4px", color: "#c62828", fontSize: "13px" } }, error),

        // 默认文种
        h(Section, { title: "基础设置" },
          h(ConfigInput, {
            label: "默认公文类型",
            value: config.default_doc_type,
            placeholder: "notice",
            onChange: function (v) { updateField("default_doc_type", v); },
          })
        ),

        // 页面设置
        h(Section, { title: "页面设置" },
          h(ConfigInput, { label: "上边距", value: config.page_setup && config.page_setup.margins && config.page_setup.margins.top, placeholder: "2.8cm", onChange: function (v) { updateField("page_setup.margins.top", v); } }),
          h(ConfigInput, { label: "下边距", value: config.page_setup && config.page_setup.margins && config.page_setup.margins.bottom, placeholder: "2.8cm", onChange: function (v) { updateField("page_setup.margins.bottom", v); } }),
          h(ConfigInput, { label: "左边距", value: config.page_setup && config.page_setup.margins && config.page_setup.margins.left, placeholder: "2.7cm", onChange: function (v) { updateField("page_setup.margins.left", v); } }),
          h(ConfigInput, { label: "右边距", value: config.page_setup && config.page_setup.margins && config.page_setup.margins.right, placeholder: "2.7cm", onChange: function (v) { updateField("page_setup.margins.right", v); } }),
          h(ConfigInput, { label: "页眉距", value: config.page_setup && config.page_setup.header_distance, placeholder: "1.5cm", onChange: function (v) { updateField("page_setup.header_distance", v); } }),
          h(ConfigInput, { label: "页脚距", value: config.page_setup && config.page_setup.footer_distance, placeholder: "2.3cm", onChange: function (v) { updateField("page_setup.footer_distance", v); } })
        ),

        // 正文格式
        h(Section, { title: "正文格式" },
          h(ConfigInput, { label: "字体", value: config.body && config.body.font, placeholder: "仿宋_GB2312", onChange: function (v) { updateField("body.font", v); } }),
          h(ConfigInput, { label: "字体回退", value: config.body && config.body.font_fallback, placeholder: "FangSong", onChange: function (v) { updateField("body.font_fallback", v); } }),
          h(ConfigInput, { label: "字号", value: config.body && config.body.size, placeholder: "16pt", onChange: function (v) { updateField("body.size", v); } }),
          h(ConfigInput, { label: "行距", value: config.body && config.body.line_spacing, placeholder: "33pt", onChange: function (v) { updateField("body.line_spacing", v); } }),
          h(ConfigInput, { label: "首行缩进", value: config.body && config.body.first_line_indent, placeholder: "2em", onChange: function (v) { updateField("body.first_line_indent", v); } }),
          h(ConfigInput, { label: "对齐方式", value: config.body && config.body.align, placeholder: "justify", onChange: function (v) { updateField("body.align", v); } })
        ),

        // 公文标题
        h(Section, { title: "公文标题" },
          h(ConfigInput, { label: "字体", value: config.doc_title && config.doc_title.font, placeholder: "方正小标宋简体", onChange: function (v) { updateField("doc_title.font", v); } }),
          h(ConfigInput, { label: "字体回退", value: config.doc_title && config.doc_title.font_fallback, placeholder: "SimSun", onChange: function (v) { updateField("doc_title.font_fallback", v); } }),
          h(ConfigInput, { label: "字号", value: config.doc_title && config.doc_title.size, placeholder: "22pt", onChange: function (v) { updateField("doc_title.size", v); } }),
          h(ConfigInput, { label: "对齐方式", value: config.doc_title && config.doc_title.align, placeholder: "center", onChange: function (v) { updateField("doc_title.align", v); } })
        ),

        // 一级标题
        h(Section, { title: "一级标题" },
          h(ConfigInput, { label: "字体", value: config.heading_1 && config.heading_1.font, placeholder: "黑体", onChange: function (v) { updateField("heading_1.font", v); } }),
          h(ConfigInput, { label: "字体回退", value: config.heading_1 && config.heading_1.font_fallback, placeholder: "SimHei", onChange: function (v) { updateField("heading_1.font_fallback", v); } }),
          h(ConfigInput, { label: "字号", value: config.heading_1 && config.heading_1.size, placeholder: "16pt", onChange: function (v) { updateField("heading_1.size", v); } }),
          h(ConfigInput, { label: "行距", value: config.heading_1 && config.heading_1.line_spacing, placeholder: "33pt", onChange: function (v) { updateField("heading_1.line_spacing", v); } })
        ),

        // 二级标题
        h(Section, { title: "二级标题" },
          h(ConfigInput, { label: "字体", value: config.heading_2 && config.heading_2.font, placeholder: "楷体_GB2312", onChange: function (v) { updateField("heading_2.font", v); } }),
          h(ConfigInput, { label: "字体回退", value: config.heading_2 && config.heading_2.font_fallback, placeholder: "KaiTi", onChange: function (v) { updateField("heading_2.font_fallback", v); } }),
          h(ConfigInput, { label: "字号", value: config.heading_2 && config.heading_2.size, placeholder: "16pt", onChange: function (v) { updateField("heading_2.size", v); } }),
          h(ConfigInput, { label: "行距", value: config.heading_2 && config.heading_2.line_spacing, placeholder: "33pt", onChange: function (v) { updateField("heading_2.line_spacing", v); } })
        ),

        // 三级标题
        h(Section, { title: "三级标题" },
          h(ConfigInput, { label: "字体", value: config.heading_3 && config.heading_3.font, placeholder: "仿宋_GB2312", onChange: function (v) { updateField("heading_3.font", v); } }),
          h(ConfigInput, { label: "字体回退", value: config.heading_3 && config.heading_3.font_fallback, placeholder: "FangSong", onChange: function (v) { updateField("heading_3.font_fallback", v); } }),
          h(ConfigInput, { label: "字号", value: config.heading_3 && config.heading_3.size, placeholder: "16pt", onChange: function (v) { updateField("heading_3.size", v); } }),
          h(ConfigInput, { label: "行距", value: config.heading_3 && config.heading_3.line_spacing, placeholder: "33pt", onChange: function (v) { updateField("heading_3.line_spacing", v); } })
        ),

        // 署名格式
        h(Section, { title: "署名格式" },
          h(ConfigInput, { label: "字体", value: config.signature && config.signature.font, placeholder: "仿宋_GB2312", onChange: function (v) { updateField("signature.font", v); } }),
          h(ConfigInput, { label: "字体回退", value: config.signature && config.signature.font_fallback, placeholder: "FangSong", onChange: function (v) { updateField("signature.font_fallback", v); } }),
          h(ConfigInput, { label: "字号", value: config.signature && config.signature.size, placeholder: "18pt", onChange: function (v) { updateField("signature.size", v); } }),
          h(ConfigInput, { label: "对齐方式", value: config.signature && config.signature.align, placeholder: "center", onChange: function (v) { updateField("signature.align", v); } })
        ),

        // 操作按钮
        h("div", { style: { display: "flex", gap: "10px", marginTop: "16px" } },
          h("button", {
            onClick: handleSave,
            disabled: saving,
            style: {
              padding: "6px 20px", fontSize: "14px", fontWeight: 600,
              border: "1px solid var(--ds-border, #ddd)", borderRadius: "4px",
              background: "var(--ds-primary, #1976d2)", color: "#fff",
              cursor: saving ? "not-allowed" : "pointer",
              opacity: saving ? 0.6 : 1,
            },
          }, saving ? "保存中..." : "💾 保存配置"),
          h("button", {
            onClick: handleReset,
            style: {
              padding: "6px 20px", fontSize: "14px",
              border: "1px solid var(--ds-border, #ddd)", borderRadius: "4px",
              background: "var(--ds-hover, #f5f5f5)", color: "var(--ds-text, #333)",
              cursor: "pointer",
            },
          }, "↩ 恢复默认"),
          h("span", { style: { fontSize: "12px", color: "var(--ds-text-secondary, #999)", alignSelf: "center" } },
            "配置文件: ~/.gongwen-skill/dsh-config.json"
          )
        )
      );
    }

    // 导出 apply + inject
    exports.apply = function (ctx) {
      var slots = ctx.get("slots");
      if (slots === undefined) return;

      // 注册到系统设置 → 插件配置
      slots.inject("settings.section", function () {
        slots.register(
          { name: "settings.section", key: "gongwen-skill" },
          function () {
            return h(GongwenConfigPanel);
          }
        );
      });
    };
    exports.inject = ["slots"];

    return module.exports;
  },
});
