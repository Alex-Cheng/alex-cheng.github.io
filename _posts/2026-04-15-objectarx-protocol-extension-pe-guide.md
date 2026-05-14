# ObjectARX Protocol Extension (PE) 深度解析：运行时类扩展的艺术

## 目录
1. [PE 是什么](#pe-是什么)
2. [PE 的设计原理](#pe-的设计原理)
3. [PE 的使用方法](#pe-的使用方法)
4. [PE 设计思想的得与失](#pe-设计思想的得与失)
5. [最佳实践与常见陷阱](#最佳实践与常见陷阱)

---

## PE 是什么

**PE** = **P**rotocol **E**xtension（协议扩展）

在 ObjectARX 中，PE 是一种**运行时类扩展机制**，允许开发者在**不修改原有类代码**、**不继承原有类**的情况下，为现有类动态添加功能。

### 为什么需要 PE？

假设你需要为 AutoCAD 内置的 `AcDbLine` 类添加一个新功能——自定义渲染逻辑。传统的 OOP 方式面临困境：

| 方案 | 问题 |
|------|------|
| 继承 `AcDbLine` | 用户必须使用你的子类才能享受功能 |
| 修改 AutoCAD 源码 | 不可能实现 |
| 全局函数 | 失去封装，无法针对不同类定制 |

**PE 提供了第四种选择**：通过 `AcRxClass`（运行时元对象）动态附加功能。

### 核心概念

```
┌─────────────────────────────────────────────────────┐
│                  PE 核心架构                           │
├─────────────────────────────────────────────────────┤
│  协议接口类 (如 IMyCustomDraw)                         │
│      ↓ 继承                                           │
│  协议实现类 (如 MyCustomDrawImpl)                      │
│      ↓ 通过 addX 附加                                  │
│  目标类的 AcRxClass (如 AcDbLine::desc())              │
└─────────────────────────────────────────────────────┘
```

---

## PE 的设计原理

### 1. 基于 AcRxClass 的元对象系统

```cpp
// rxclass.h - AcRxClass 核心方法
class AcRxClass: public AcRxObject
{
public:
    ACBASE_PORT AcRxObject* addX(AcRxClass* protocolClass, AcRxObject* pExt);
    ACBASE_PORT AcRxObject* queryX(const AcRxClass* protocolClass) const;
    ACBASE_PORT AcRxObject* delX(AcRxClass* protocolClass);
    // ...
};
```

**关键设计决策**：功能扩展绑定到类的元对象（`AcRxClass`），而非实例对象。这意味着：
- 所有 `AcDbLine` 实例共享同一个 PE
- 扩展在类级别生效

### 2. Protocol Extension vs Protocol Reactor vs Overrule

ObjectARX 提供了三种基于 PE 的扩展模式：

| 模式 | 注册方式 | 特点 | 适用场景 |
|------|----------|------|----------|
| **基础 PE** | `addX()` | 一对一，单扩展对象 | 为类附加单一功能 |
| **Protocol Reactor** | `ACRX_PROTOCOL_REACTOR_LIST_AT()->addReactor()` | 一对多，多监听者 | 事件通知、多模块监听 |
| **Overrule** | `AcRxOverrule::addOverrule()` | 覆盖/重载原有行为 | 修改 AutoCAD 内置行为 |

### 3. 类层次与伪构造函数

PE 机制依赖于 ObjectARX 的**运行时类型识别系统**：

```cpp
// rxboiler.h - 宏定义展开
#define ACRX_DECLARE_MEMBERS(CLASS_NAME) \
    static AcRxClass* desc();      /* 获取类描述符 */ \
    static CLASS_NAME* cast(const AcRxObject* inPtr); \
    static void rxInit();           /* 注册类 */ \
    // ...
```

每个 PE 类都需要通过 `rxInit()` 注册到系统，才能参与 PE 机制。

---

## PE 的使用方法

### 完整示例：为 AcDbCircle 添加自定义数据协议

#### 步骤 1：定义 PE 接口类

```cpp
// ICustomData.h
#pragma once
#include "rxobject.h"
#include "rxboiler.h"

// 协议接口：定义功能契约
class ICustomData : public AcRxObject
{
public:
    ACRX_DECLARE_MEMBERS(ICustomData);
    
    // 协议方法：获取自定义属性
    virtual int getPriority() const = 0;
    virtual const wchar_t* getCategory() const = 0;
    virtual void serialize(void* buffer, size_t size) const = 0;
};

// ICustomData.cpp
#include "ICustomData.h"
ACRX_NO_CONS_DEFINE_MEMBERS(ICustomData, AcRxObject)
```

#### 步骤 2：实现 PE 类

```cpp
// CircleDataImpl.h
#pragma once
#include "ICustomData.h"

class CircleDataImpl : public ICustomData
{
public:
    ACRX_DECLARE_MEMBERS(CircleDataImpl);
    
    CircleDataImpl() : m_priority(100), m_category(L"Geometry") {}
    
    virtual int getPriority() const override { return m_priority; }
    virtual const wchar_t* getCategory() const override { return m_category; }
    virtual void serialize(void* buffer, size_t size) const override;
    
    void setPriority(int p) { m_priority = p; }
    
private:
    int m_priority;
    const wchar_t* m_category;
};

// CircleDataImpl.cpp
#include "CircleDataImpl.h"
ACRX_CONS_DEFINE_MEMBERS(CircleDataImpl, ICustomData, 0)

void CircleDataImpl::serialize(void* buffer, size_t size) const
{
    // 实现序列化逻辑
    if (buffer && size >= sizeof(int)) {
        memcpy(buffer, &m_priority, sizeof(int));
    }
}
```

#### 步骤 3：注册 PE

```cpp
// acrxEntryPoint.cpp
#include "ICustomData.h"
#include "CircleDataImpl.h"

static CircleDataImpl* g_pCircleData = nullptr;

void initApp()
{
    // 1. 注册 PE 接口类
    ICustomData::rxInit();
    
    // 2. 注册 PE 实现类
    CircleDataImpl::rxInit();
    
    // 3. 构建类层次（必须！）
    acrxBuildClassHierarchy();
    
    // 4. 创建 PE 实例并附加到目标类
    g_pCircleData = new CircleDataImpl();
    AcDbCircle::desc()->addX(ICustomData::desc(), g_pCircleData);
    
    // 5. 注册测试命令
    acedRegCmds->addCommand(L"PE_DEMO", L"TESTPE", L"testpe", 
        ACRX_CMD_MODAL, testPECommand);
}

void unloadApp()
{
    // 清理：必须按相反顺序删除
    if (g_pCircleData) {
        AcDbCircle::desc()->delX(ICustomData::desc());
        delete g_pCircleData;
        g_pCircleData = nullptr;
    }
    
    deleteAcRxClass(CircleDataImpl::desc());
    deleteAcRxClass(ICustomData::desc());
    
    acedRegCmds->removeGroup(L"PE_DEMO");
}
```

#### 步骤 4：查询和使用 PE

```cpp
void testPECommand()
{
    // 获取用户选择的实体
    ads_name en;
    ads_point pt;
    
    if (acedEntSel(L"\nSelect a circle: ", en, pt) != RTNORM) {
        acutPrintf(L"No selection.\n");
        return;
    }
    
    AcDbObjectId id;
    acdbGetObjectId(id, en);
    
    AcDbEntity* pEnt = nullptr;
    if (acdbOpenObject(pEnt, id, AcDb::kForRead) != Acad::eOk) {
        return;
    }
    
    // ========== 查询 PE（推荐方式）==========
    ICustomData* pData = ACRX_PE_PTR(pEnt, ICustomData);
    
    if (pData) {
        acutPrintf(L"Entity has custom data!\n");
        acutPrintf(L"  Priority: %d\n", pData->getPriority());
        acutPrintf(L"  Category: %ls\n", pData->getCategory());
    } else {
        acutPrintf(L"Entity does not support ICustomData protocol.\n");
    }
    
    pEnt->close();
}

// ========== 批量查询示例 ==========
void queryAllEntities()
{
    AcDbBlockTable* pBt = nullptr;
    acdbHostApplicationServices()->workingDatabase()
        ->getBlockTable(pBt, AcDb::kForRead);
    
    AcDbBlockTableRecord* pMs = nullptr;
    pBt->getAt(ACDB_MODEL_SPACE, pMs, AcDb::kForRead);
    pBt->close();
    
    AcDbBlockTableRecordIterator* pIter = nullptr;
    pMs->newIterator(pIter);
    
    for (; !pIter->done(); pIter->step()) {
        AcDbEntity* pEnt = nullptr;
        if (pIter->getEntity(pEnt, AcDb::kForRead) == Acad::eOk) {
            
            // 查询 PE
            ICustomData* pData = ACRX_PE_PTR(pEnt, ICustomData);
            if (pData) {
                acutPrintf(L"%ls supports ICustomData\n", 
                    pEnt->isA()->name());
            }
            
            pEnt->close();
        }
    }
    
    delete pIter;
    pMs->close();
}
```

---

## PE 设计思想的得与失

### 优点 ✅

| 优点 | 说明 |
|------|------|
| **非侵入式扩展** | 无需修改目标类源码，也无需继承 |
| **运行时动态** | 可在程序启动后动态附加/移除 |
| **类级别生效** | 所有实例自动获得扩展功能 |
| **多协议支持** | 一个类可同时支持多种 PE |
| **第三方友好** | 任何应用都可给其他类添加 PE |

### 缺点与挑战 ⚠️

| 缺点 | 说明 | 应对策略 |
|------|------|----------|
| **单例限制** | 基础 PE 是单例模式，所有实例共享同一个 PE 对象 | 使用 Protocol Reactor 支持多实例 |
| **生命周期管理** | PE 对象生命周期需手动管理 | 在 `kUnloadAppMsg` 中清理 |
| **类型安全** | `queryX` 返回 `AcRxObject*`，需手动 cast | 使用 `ACRX_PE_PTR` 宏 |
| **无实例隔离** | 无法为单个对象实例附加不同 PE | 在 PE 实现中通过参数区分 |
| **学习曲线** | 涉及多个类：AcRxClass、rxInit、宏等 | 遵循标准模板 |

### 与其他语言的对比

| 语言/平台 | 类似机制 | 对比 |
|----------|---------|------|
| C++ | 多重继承 + 虚继承 | PE 更灵活，无菱形继承问题 |
| Java | Interface + 动态代理 | PE 绑定到类而非实例 |
| C# | Extension Methods | PE 是真正的对象，可有状态 |
| Python | Monkey Patching | PE 类型安全，更可控 |

---

## 最佳实践与常见陷阱

### 最佳实践 ✅

#### 1. 总是使用 ACRX_PE_PTR 宏

`ACRX_PE_PTR` 是 PE 查询的语法糖，定义于 `rxboiler.h`：

```cpp
#define ACRX_PE_PTR(pObj, ProtocolClass) \
    ProtocolClass::cast((pObj)->isA()->queryX(ProtocolClass::desc()))
```

三步分解：

1. `pObj->isA()` — 获取对象的 `AcRxClass*`
2. `->queryX(ProtocolClass::desc())` — 在类元对象中查找 PE
3. `ProtocolClass::cast()` — 安全类型转换

```cpp
// 推荐 ✅
IMyProtocol* pProto = ACRX_PE_PTR(pEnt, IMyProtocol);

// 手写 ❌（冗长且易错）
AcRxObject* pObj = pEnt->isA()->queryX(IMyProtocol::desc());
IMyProtocol* pProto = IMyProtocol::cast(pObj);
```

#### 2. 始终检查返回值

```cpp
IMyProtocol* pProto = ACRX_PE_PTR(pEnt, IMyProtocol);
if (pProto) {
    // 使用 PE
} else {
    // 优雅降级
    acutPrintf(L"Protocol not supported\n");
}
```

#### 3. 严格管理生命周期

```cpp
// 推荐：在卸载时清理
void unloadApp()
{
    // 1. 先 detach PE
    AcDbCircle::desc()->delX(ICustomData::desc());
    
    // 2. 再删除 PE 对象
    delete g_pCircleData;
    g_pCircleData = nullptr;
    
    // 3. 最后删除类定义
    deleteAcRxClass(CircleDataImpl::desc());
    deleteAcRxClass(ICustomData::desc());
}
```

#### 4. 区分接口与实现

```cpp
// PE 接口应该纯虚，无状态
class IMyProtocol : public AcRxObject {
    virtual void doSomething() = 0;
};

// 实现类可以有自己的状态
class MyProtocolImpl : public IMyProtocol {
    int m_counter = 0;  // 实现类可以有状态
    virtual void doSomething() override { m_counter++; }
};
```

### 常见陷阱 ❌

#### 陷阱 1：忘记调用 acrxBuildClassHierarchy()

```cpp
void initApp()
{
    MyProtocol::rxInit();
    // 错误！忘记调用 acrxBuildClassHierarchy()
    
    // 后续 queryX 会失败！
}
```

#### 陷阱 2：在卸载时顺序错误

```cpp
void unloadApp()
{
    // 错误顺序！先删除对象再 detach
    delete g_pPE;  // ❌ 错误！
    AcDbCircle::desc()->delX(IMyProtocol::desc());
}
```

#### 陷阱 3：使用已废弃的 getX()

```cpp
// 废弃 ❌
AcRxObject* pObj = pClass->getX(protocolClass);

// 推荐 ✅
AcRxObject* pObj = pClass->queryX(protocolClass);
```

#### 陷阱 4：假设所有实体都有 PE

```cpp
// 危险！
IMyProtocol* p = ACRX_PE_PTR(pEnt, IMyProtocol);
p->doSomething();  // 如果 p 为 nullptr，崩溃！
```

#### 陷阱 5：替换 PE 时忽略 addX() 的返回值

`addX()` 返回被替换的**旧扩展对象**（首次注册返回 `nullptr`）。直接丢弃返回值会导致旧对象泄漏。

```cpp
// ❌ 错误：循环中重复 addX，旧对象泄漏
while (someCondition) {
    MyProtocol* p = new MyProtocol();
    SomeClass::desc()->addX(MyProtocol::desc(), p);
    // 第2次起，addX 返回的旧指针被丢弃 → 泄漏
}

// ⚠️ 更危险：在 addX 后直接 delete
SomeClass::desc()->addX(MyProtocol::desc(), new MyProtocol());
delete p;  // ❌ 系统内部仍持有这个指针 → use-after-free！

// ✅ 正确：接收 addX 的返回值，安全释放旧对象
while (someCondition) {
    MyProtocol* pOld = static_cast<MyProtocol*>(
        SomeClass::desc()->addX(MyProtocol::desc(), new MyProtocol()));
    if (pOld) delete pOld;  // 首次注册 pOld 为 nullptr，无需释放
}
```

---

## 总结

Protocol Extension 是 ObjectARX 中**最强大也最被低估**的机制之一。它提供了：

1. **开放封闭原则**的完美实践
2. **运行时类扩展**的能力
3. **非侵入式第三方扩展**的途径

掌握 PE 机制，能让你在 ObjectARX 开发中实现更优雅、更可维护的设计。

### 推荐阅读

- SDK 示例：`samples\reactors\ProtocolReactors_dg\`
- 头文件：`inc\rxclass.h`, `inc\rxobject.h`, `inc\rxprotevnt.h`
- 相关概念：AcRxClass、ACRX_PE_PTR 宏、Protocol Extension

---

*本文基于 ObjectARX SDK 2024，适用于 AutoCAD 2024 开发。*
