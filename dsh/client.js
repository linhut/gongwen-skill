// 公文全流程处理专家 DSH client — 设置平级菜单「文档样式配置」（gongwen-skill）
// (c) 2026 Jose AI (https://www.linhut.cn)
// https://github.com/linhut/gongwen-skill
// Licensed under the MIT License. See the LICENSE file for details.
//
// 兼容目标：DSH 0.1.2+ ~ 0.2.3+
//   - 0.2.x：数据源 = ctx.configForms.get(entryId)（entryId === 命名空间）
//   - 0.1.x：数据源 = ctx.settingsScope.bind({namespace})（降级路径）
//   - 槽位访问：ctx.slots 优先，旧版退回 ctx.get("slots")
//   - 只声明 inject = ['slots']：0.2.x 没有 settingsScope，写进 inject 会导致整页永不激活
//
// 官方依据：dsh-client-ui-settings / dsh-client-ui-settings-general
//   - 设置页面注册进 settings.section；导航 label 由 resolveSlotLabel 解析
//   - 样式只用 --dsw-alias-* 语义 token
//   - 打包格式 = loader 的 lazy-CJS factory（window.__ModuleLoader__.load）

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

    // 与 Host 侧 Config / settings.register 配对的命名空间
    var NS = "gongwen-skill";

    // 25 种公文类型（与 rules/official/*.yaml 及 list-types 输出一致）
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
    // 与 dsh/index.js 的 Config（0.2.x）/ settings schema（0.1.x）保持一一对应
    var FIELDS = [
      { path: ["default_doc_type"], label: "默认公文类型", placeholder: "notice", type: "select" },

      { path: ["page_setup", "margins", "top"], label: "上边距", placeholder: "2.8cm", type: "text" },
      { path: ["page_setup", "margins", "bottom"], label: "下边距", placeholder: "2.8cm", type: "text" },
      { path: ["page_setup", "margins", "left"], label: "左边距", placeholder: "2.7cm", type: "text" },
      { path: ["page_setup", "margins", "right"], label: "右边距", placeholder: "2.7cm", type: "text" },
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

    // 快照归一化：configForms 与 settingsScope 的字段略有差异
    function normalizeSnapshot(s) {
      if (!s) return { status: "unavailable", value: null, base: null, user: null, writable: false };
      return {
        status: s.status || (s.value !== undefined ? "ready" : "loading"),
        value: s.value,
        base: s.base,
        user: s.user,
        writable: s.writable !== false,
        revision: s.revision,
      };
    }

    // ---- 数据源绑定：0.2.x configForms 优先，0.1.x settingsScope 降级 ----
    // 注意：Cordis 4.1 禁止未声明 inject 就访问 ctx.<service>，因此只用 ctx.get(name) 探测，
    // 不做 ctx.configForms / ctx.settingsScope 属性兜底（会抛错并静默降级为只读）。
    function createBinding(ctx) {
      var forms = null;
      var scopeApi = null;
      try {
        forms = ctx.get ? ctx.get("configForms") : null;
      } catch (_) {}
      if (forms && typeof forms.get === "function") {
        try {
          var form = forms.get(NS);
          if (form) {
            return {
              kind: "configForms",
              read: function () { return normalizeSnapshot(form.getSnapshot()); },
              write: function (ops, revision) { return form.mutate(ops, revision); },
              subscribe: function (cb) {
                try { return form.subscribe(cb); } catch (_) { return function () {}; }
              },
            };
          }
        } catch (_) {
          // 命名空间尚未被服务：落到降级路径
        }
      }

      try {
        scopeApi = ctx.get ? ctx.get("settingsScope") : null;
      } catch (_) {}
      if (scopeApi && typeof scopeApi.bind === "function") {
        var scope = scopeApi.bind({ namespace: NS });
        return {
          kind: "settingsScope",
          read: function () { return normalizeSnapshot(scope.getSnapshot()); },
          write: function (ops) { return scope.mutate(ops); },
          subscribe: function (cb) {
            try { return scope.subscribe(cb); } catch (_) { return function () {}; }
          },
        };
      }

      return null;
    }

    // ---- 配置 controller：暂存编辑 → 一次性提交（带 revision 防覆盖）----
    function makeController(ctx) {
      var binding = null;
      var snapshot = normalizeSnapshot(null);
      var staged = {}; // pathKey -> { value, clear }
      var saving = false;
      var failed = false;
      var message = "";
      var listeners = [];

      function resolve() {
        if (binding) return binding;
        binding = createBinding(ctx);
        return binding;
      }

      function emit() {
        for (var i = 0; i < listeners.length; i++) {
          try { listeners[i](); } catch (_) {}
        }
      }

      function refresh() {
        var b = resolve();
        if (b) {
          retries = 0;
          try { snapshot = b.read(); } catch (_) { snapshot = normalizeSnapshot(null); }
          ensureSubscribed();
        } else {
          snapshot = normalizeSnapshot(null);
          scheduleRetry();
        }
        emit();
      }

      var retries = 0;
      function scheduleRetry() {
        if (retries >= 6) return;
        retries++;
        try {
          var t = setTimeout(refresh, 500);
          if (t && typeof t.unref === "function") t.unref();
        } catch (_) {}
      }

      var unsubscribe = null;
      function ensureSubscribed() {
        if (unsubscribe || !binding) return;
        try {
          unsubscribe = binding.subscribe(function () {
            try { snapshot = binding.read(); } catch (_) {}
            emit();
          });
        } catch (_) {}
      }

      refresh();

      function pathKey(path) { return path.join("."); }

      function fieldValue(path) {
        var k = pathKey(path);
        if (Object.prototype.hasOwnProperty.call(staged, k)) return staged[k].clear ? undefined : staged[k].value;
        return getPath(snapshot.value, path);
      }

      function fieldOverridden(path) {
        var k = pathKey(path);
        if (Object.prototype.hasOwnProperty.call(staged, k)) return !staged[k].clear;
        // user 层中出现该字段即视为用户覆盖（官方语义：presence，不是值比较）
        return getPath(snapshot.user, path) !== undefined;
      }

      function setField(path, value) {
        staged[pathKey(path)] = { value: value, clear: false };
        failed = false;
        message = "";
        emit();
      }

      function clearField(path) {
        staged[pathKey(path)] = { value: undefined, clear: true };
        failed = false;
        message = "";
        emit();
      }

      function dirty() {
        for (var k in staged) {
          if (Object.prototype.hasOwnProperty.call(staged, k)) return true;
        }
        return false;
      }

      // 只对"用户层真实存在覆盖"的字段发 unset，避免对继承值发无意义清除
      function resetAll() {
        var b = resolve();
        if (!b) return;
        staged = {};
        var any = false;
        for (var i = 0; i < FIELDS.length; i++) {
          var f = FIELDS[i];
          if (getPath(snapshot.user, f.path) !== undefined) {
            staged[pathKey(f.path)] = { value: undefined, clear: true };
            any = true;
          }
        }
        failed = false;
        message = any ? "已恢复默认值（需点击保存生效）" : "当前没有自定义项，无需恢复";
        emit();
      }

      function save() {
        if (saving) return;
        var b = resolve();
        if (!b) {
          failed = true;
          message = "保存失败：设置服务不可用";
          emit();
          return;
        }
        var ops = [];
        for (var k in staged) {
          if (!Object.prototype.hasOwnProperty.call(staged, k)) continue;
          var edit = staged[k];
          var path = k.split(".");
          if (edit.clear) ops.push({ op: "unset", path: path });
          else ops.push({ op: "set", path: path, value: edit.value });
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

        var revision = snapshot.revision;
        var pending;
        try {
          pending = b.write(ops, revision);
        } catch (e) {
          saving = false;
          failed = true;
          message = "保存失败：" + (e && e.message ? e.message : "未知错误");
          emit();
          return;
        }

        Promise.resolve(pending)
          .then(function () {
            saving = false;
            staged = {};
            message = "✅ 配置已保存" + (b.kind === "configForms"
              ? "（已写入插件设置文档）"
              : "（已同步到 ~/.gongwen-skill/dsh-config.json）");
            emit();
            refresh();
          })
          .catch(function (e) {
            saving = false;
            failed = true;
            var msg = e && e.message ? String(e.message) : "未知错误";
            if (/conflict|revision|stale/i.test(msg)) {
              message = "保存冲突：配置已被其他窗口修改。已为你刷新最新值，请核对后重试。";
              staged = {};
              refresh();
            } else {
              message = "保存失败：" + msg;
            }
            emit();
          });
      }

      return {
        kind: function () { return binding ? binding.kind : "none"; },
        getSnapshot: function () {
          return {
            status: snapshot.status,
            writable: snapshot.writable,
            saving: saving,
            failed: failed,
            message: message,
            dirty: dirty(),
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
            style: { minWidth: "140px", flexShrink: 0, color: "var(--dsw-alias-label-secondary)" },
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
              color: overridden ? "var(--dsw-alias-label-secondary)" : "var(--dsw-alias-label-tertiary)",
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
          style: { minWidth: "140px", flexShrink: 0, color: "var(--dsw-alias-label-secondary)" },
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
            color: overridden ? "var(--dsw-alias-label-secondary)" : "var(--dsw-alias-label-tertiary)",
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
          style: { fontSize: "13px", fontWeight: 600, padding: "0 8px", color: "var(--dsw-alias-label-primary)" },
        }, props.title),
        props.children,
      );
    }

    // ---- 设置页「文档样式配置」主组件（settings.section 内容）----
    function GongwenStylesSection(props) {
      var face = props.face;
      var state = useState(0);
      var force = state[1];

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

      var sourceLabel = face.kind() === "configForms"
        ? "数据源：插件设置文档（configForms）"
        : face.kind() === "settingsScope"
          ? "数据源：旧版设置命名空间（settingsScope）"
          : "数据源：不可用";

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
        }, "设置服务不可用（当前宿主未提供 configForms / settingsScope），排版参数区只读。"),

        renderGroup("基础设置", FIELDS.slice(0, 1)),
        renderGroup("页面设置", FIELDS.slice(1, 5)),

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
              color: meta.dirty ? "var(--dsw-alias-label-warning, #b26a00)" : "var(--dsw-alias-label-tertiary)",
            },
          }, meta.dirty ? "有未保存修改" : "已同步"),
        ),

        h("div", {
          style: {
            marginTop: "10px", fontSize: "11px", lineHeight: "1.5",
            color: "var(--dsw-alias-label-tertiary)",
          },
        }, sourceLabel + "｜CLI 缓存: ~/.gongwen-skill/dsh-config.json"),
      );
    }

    // 导出 apply + inject（官方 Client UI & Slots 注册方式）
    exports.apply = function (ctx) {
      var slots = null;
      try {
        slots = ctx.slots || ctx.get("slots");
      } catch (_) {}
      if (!slots || typeof slots.register !== "function") {
        try { ctx.logger && ctx.logger.warn && ctx.logger.warn("gongwen-skill: 无 slots 服务，跳过设置页注册"); } catch (_) {}
        return;
      }

      var controller = makeController(ctx);

      // 注册设置侧边栏平级菜单「文档样式配置」
      var registerSection = function () {
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
      };
      if (typeof slots.inject === "function") {
        slots.inject("settings.section", registerSection);
      } else {
        registerSection();
      }

      // 插件卸载时释放订阅
      try {
        ctx.effect(function () {
          return function () { controller.dispose(); };
        }, "gongwen-skill: client controller cleanup");
      } catch (_) {
        // 无 effect 服务时忽略（旧版）
      }
    };
    exports.inject = ["slots"];

    return module.exports;
  },
});
