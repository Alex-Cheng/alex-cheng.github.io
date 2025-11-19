# AcRxObject 的最佳实践

## 简介

在 AutoCAD、ODA Teigha、GstarCAD 等 CAD 平台中，**AcRxObject** 是整个运行时类型系统（RTTI）的核心。任何需要支持 **DWG 持久化、运行时反射、动态构造、命令交互** 的类，几乎都建立在 AcRxObject 框架之上。

然而在工程实践中，许多团队在使用 AcRxObject 时存在以下常见问题：

* 宏选择混乱（DEFINE / CONS / EX / EX2 / ALTNAME）
* RxClass 未注册导致崩溃或内存泄漏
* DWG 读写版本不兼容
* 插件模块加载或卸载异常

本文从工程最佳实践出发，总结一套**RxObject 派生类设计方法**。

如果不理解 RxObject 背后的类型注册机制，很容易在大型 CAD 系统中引入潜在的不稳定因素。  
本文从工程设计与架构角度出发，系统总结一套可靠的 **RxObject 派生类设计方法与最佳实践**。

---

## 一、RxObject 是什么？为什么 AutoCAD/GstarCAD/ODA 系统都需要它？

在传统 C++ 中：

* 类型识别依赖 RTTI（typeid, dynamic_cast）
* 对象不能动态构造
* 类型元信息不能反射查询
* 序列化系统需要额外映射

CAD 系统比一般应用更复杂：

* DWG 文件必须写入类名、版本信息
* 插件动态加载，需要注册自定义图元
* 命令系统需要按类名创建对象
* 运行时要支持 “isA/isKindOf”
* 代理对象（Proxy）需要类元数据

因此，AutoCAD/GstarCAD/ODA 决定构建自己的“类型反射系统”：

```
AcRxObject  ← 所有可反射对象的基类
AcRxClass   ← 类的元信息（名称、父类、构造函数）
```

只要继承 AcRxObject，你的类就能：

* 被 DWG 持久化
* 被 AutoCAD 命令系统动态创建
* 进行反射查询
* 被插件管理器识别与注册

---

## 二、什么时候应该让类继承 AcRxObject？

这是工程中最重要的决策点。

### 必须继承（强绑定到 CAD 运行时）

* AcDbObject / AcDbEntity 派生类
* 所有 DWG 可序列化对象
* 所有需要动态创建的类
* 所有需要反射（desc/isA）的类
* 需要注册的图元 / 特性类
* 对象代理系统（Proxy Object）的实体类型

### 不应该继承（保持普通 C++ 类）

* 几何算法类（如 NURBS、三角化）
* 工具辅助类
* 其他普通类

**能不用 AcRxObject，就绝不用**。

遵循奥卡姆剃刀原则。

---

## 三、为什么需要注册 RxClass  

在 C++ 中，`class` 只是编译期概念，而在 Object ARX 的运行时世界中，**每个需要类型反射系统管理的 AcRxObject 派生类都必须在运行时登记**。  
登记的载体就是 `AcRxClass` —— 它是类的“元信息（MetaClass）”，包含：

| 字段 | 含义 |
|------|------|
| 类名 (`name()`) | 对应 C++ 类名或注册名 |
| 父类 (`myParent()`) | 建立继承层次结构 |
| 构造函数回调 (`constructor()`) | 用于动态实例化 |
| 版本信息 (`dxfName`, `dwgVersion`) | 保证 DWG 读写兼容 |
| 代理属性 (`proxyFlags`) | 控制代理绘制和行为 |

AutoCAD 通过这个 RxClass 注册表来：

* 从类名找到类型描述；
* 判断继承关系（isA / isKindOf）；
* 创建对象；
* 执行序列化 / 反序列化；
* 管理 DWG 文件读写。  

如果没有正确注册，AutoCAD 会在加载 DWG 时提示  
> “Unknown class … replaced by Proxy”  
或直接崩溃。  

因此，每个使用 `ACRX_XXX_DEFINE_MEMBERS...` 宏的类，都必须在模块初始化时执行：

```cpp
MyClass::rxInit();
acrxBuildClassHierarchy();
```

并在卸载时执行：

```cpp
MyClass::rxUninit();
```

这就是所谓的“注册 / 反注册 RxClass”的完整生命周期。

---

## 四、如何选择正确的 RxObject 类定义宏  


| 宏名称 | 用途说明 | 是否允许实例化 | 是否写入/读取 DWG 文件 | 注册内容 | 常见使用场景 |
|--------|-----------|----------------|--------------------------|------------|---------------|
| **`ACRX_NO_CONS_DEFINE_MEMBERS(CLASS_NAME, PARENT_CLASS)`** | 用于**抽象类**或任何**不应被实例化**的类 | ❌ 否（不注册构造函数） | ❌ 否 | 注册类描述（`AcRxClass`）、`desc()`、`isA()`，但无工厂函数 | 抽象基类、接口类、中间框架类 |
| **`ACRX_CONS_DEFINE_MEMBERS(CLASS_NAME, PARENT_CLASS, VERNO)`** | 用于能够实例化但**不参与文件持久化**的类（即瞬态类） | ✅ 是 | ❌ 否 | 注册类描述、`desc()`、`isA()`、构造器函数指针 | 命令临时对象、内存态数据结构 |
| **`ACRX_DXF_DEFINE_MEMBERS(CLASS_NAME, PARENT_CLASS, DWG_VER, MAINT_VER, PROXY_FLAGS, DXF_NAME, APP)`** | 用于能**写入/读取 DWG 或 DXF 文件**的类 | ✅ 是 | ✅ 是 | 注册类描述、构造函数、DWG/DXF 版本信息、代理标志 | 自定义图元（`AcDbEntity`）、可持久化业务对象 |
| **`ACRX_DEFINE_MEMBERS(CLASS_NAME)`** | 仅定义基础反射函数（`desc()` / `isA()`），不注册 `rxInit()`，需手动创建 `AcRxClass` | 取决于开发者是否实现构造器 | 取决于自定义 `rxInit()` 实现 | 定义反射接口 | 自定义特殊注册流程的类（高级用法） |

---

**使用建议**

1. **抽象类 →** `ACRX_NO_CONS_DEFINE_MEMBERS`  
2. **瞬态类（内存对象） →** `ACRX_CONS_DEFINE_MEMBERS`  
3. **持久化类（写 DWG/DXF） →** `ACRX_DXF_DEFINE_MEMBERS`  
4. **自定义初始化逻辑 →** `ACRX_DEFINE_MEMBERS`  

**一句话总结**

> - `NO_CONS` → 不可实例化（仅有类型信息）  
> - `CONS` → 可实例化但不持久化  
> - `DXF` → 可实例化且参与 DWG/DXF I/O  
> - `DEFINE` → 手动控制注册流程  

---

## 五、最佳实践总结


### 1. 不需要持久化的、不需要类型反射的类不要继承 RxObject

保持轻量、保持清晰。遵循奥卡姆剃刀原则。

---

### 2. 需要使用反射机制的 RxObject 都必须用RX宏族并注册RxClass

如果派生了RxObject但是并不需要反射机制，则可以不要使用Rx宏族和注册RxClass。比如GcApcAtom作为基类已经继承了RxObject，它的派生类不得不间接继承RxObject，但是实际上并不需要反射机制，那么就简单继承即可，不需要做下面的事项。

在需要反射机制的时候（很多RxObject派生类均需要，因为很多功能诸如序列化/反序列化都间接用到反射），需要使用宏族 ACRX_XXX_DEFINE_MEMBERS、ACRX_XXX_DEFINE_MEMBERS_EX 等，并且都必须通过 `rxInit/rxUninit` 注册和反注册RxClass。这样ARX运行时就掌握了这些RxObject派生类的元信息。

---

### 3. 所有可序列化类必须实现 DWG/DXF IO

```cpp
Acad::ErrorStatus dwgInFields(Filer*)
Acad::ErrorStatus dwgOutFields(Filer*)
```

否则写入/读取 DWG 将崩溃或数据丢失。

---

### 4. 避免在构造函数里做重操作（延迟到 subOpen() 或 createInstance()）

RxClass 在模块加载时就会扫描创建对象，构造函数过重会导致性能下降。

---

### 5. 用 ALTNAME 保持兼容性，不要改 DxfName

* 不能随便改 DxfName（破坏旧 DWG）
* 可以给新类加 `ALTNAME`
* 这样旧文件仍能被识别

---

### 6. 类型层次尽量稳定，避免破坏 isA/isKindOf 逻辑

例如，改变父类类型会严重损坏：

* DWG 结构
* 代理系统
* 插件的类型判断

CAD 系统不是普通应用，类体系必须长期兼容。

---

### 7. rxInit 之后必须调用 `acrxBuildClassHierarchy`

`acrxBuildClassHierarchy()` 的作用是 **在所有类注册完成后，构建继承关系表**，让 `isA()` / `isKindOf()` 等函数能够正确工作。  
正确的流程应为：

```cpp
BaseClass::rxInit();
DerivedClass::rxInit();
acrxBuildClassHierarchy();
```

在卸载时：
```cpp
DerivedClass::rxUninit();
BaseClass::rxUninit();
```

---

## 结语

AcRxObject 是 CAD 内核中最重要的抽象基类——它把普通的 C++ 类型变成了 AutoCAD 能识别、能保存、能交互的“可反射类型”。  
理解并正确使用它，是编写稳定 ARX 模块的基础。
