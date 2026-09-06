// 公文全流程处理工具 DSH client — 可视化配置卡片（gongwen-skill）
// (c) 2026 Jose AI (https://www.linhut.cn)
// https://github.com/linhut/gongwen-skill
// Licensed under the MIT License. See the LICENSE file for details.
//
// 官方依据：DeepSeek Harness Bluebook Developer Guide · Client UI & Slots
//   - 只写纯 JavaScript：无 TS/JSX/import/require，React 用 React.createElement
//   - UI 必须注册到已查询的 Slot（settings.plugin.item，keyed），apply() 不直接返回元素
//   - 通过 ctx.settingsScope.bind({ namespace }) 读写官方 settings 命名空间（revision 设栅）
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

    // 与 Host 侧 ctx.settings.register 配对的命名空间
    var NS = "gongwen-skill";

    // 扁平字段表：path（嵌套数组）、label、placeholder、type（text|checkbox）
    // 与 dsh/index.js 的 settings schema 保持一一对应
    var FIELDS = [
      { path: ["default_doc_type"], label: "默认公文类型", placeholder: "notice", type: "text" },

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

    // ---- 卡片 controller：暂存编辑 → scope.mutate 一次性提交 ----
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

    function GongwenCard(props) {
      var face = props.face;
      var [, force] = useState(0);
      useEffect(function () {
        return face.subscribe(function () { force(function (n) { return n + 1; }); });
      }, [face]);

      var meta = face.getSnapshot();
      var unavailable = meta.status !== "ready";
      var disabled = !meta.writable || meta.saving || unavailable;

      // 按组渲染
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
          padding: "16px 4px", maxWidth: "720px",
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
        }, "设置服务不可用（当前部署未挂载 settings provider），卡片只读。"),

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
      );
    }

    // 导出 apply + inject（官方 Client UI & Slots 注册方式）
    exports.apply = function (ctx) {
      var slots = ctx.get("slots");
      var settingsScope = ctx.get("settingsScope");
      if (!slots || !settingsScope) return;

      var scope = settingsScope.bind({ namespace: NS });
      var controller = makeCardController(scope);

      // 注册进官方插件配置卡片 slot（keyed：以命名空间为键）
      slots.inject("settings.plugin.item", function () {
        return slots.register({
          name: "settings.plugin.item",
          key: NS,
          locale: "settings.gongwenSkill",
          inject: function () {
            return { face: controller };
          },
        }, GongwenCard);
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
