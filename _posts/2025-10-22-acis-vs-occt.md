# 几何建模引擎 ACIS 与 OCCT 的介绍和使用场景分析

## ACIS与OCCT简介

### ACIS

**ACIS** 是由 **Spatial Corporation** 提供的三维几何建模内核，广泛应用于 CAD、CAM、CAE 等多个领域。它提供了强大的 B-Rep（边界表示）几何建模能力，支持曲线、曲面、实体、布尔运算、以及高级几何操作。

> **Spatial Corporation** 是 **Dassault Systèmes** 的子公司，专注于为各种应用提供三维建模技术。

ACIS 的架构包括：

* **ENTITY**（大写类）: 提供拓扑结构的统一接口（如 BODY、EDGE、FACE）。
* **curve / surface**（小写类）: 提供几何描述（如线、面、曲面）。

ACIS 是一个商业内核，具有成熟的技术支持、优化良好的性能和稳定性，适用于高鲁棒性的工程应用。

---

### OCCT

**OCCT**（Open Cascade Technology）是一个开源的三维几何建模内核，由 Open Cascade 提供，广泛应用于开源 CAD 软件（如 FreeCAD）和科研、教育领域。它同样提供强大的几何建模能力，支持 B-Rep 模型、布尔运算、几何优化、数据交换（如 STEP、IGES）等功能。OCCT 的特点是：

* **TopoDS_Shape**（类）: 拓扑表示与几何表示分离，提供了更强的模块化与扩展性。
* **Geom_Curve / Geom_Surface**（类）: 几何体的精确定义。

OCCT 的优势在于开源、灵活和可定制，适合对内核进行深度开发的应用。

---

## ACIS与OCCT的特点对比

### 总体定位对比

| 项目        | **ACIS**                           | **OCCT**                     |
| --------- | ---------------------------------- | ---------------------------- |
| **类型**    | 商业闭源内核                             | 开源内核                         |
| **授权模式**  | 商业付费许可                             | LGPL 或商业许可                   |
| **主要语言**  | C++                                | C++                          |
| **主要使用方** | AutoCAD、Solid Edge、IronCAD 等商业 CAD | FreeCAD、Salome、开源 CAD / 自研系统 |
| **适合人群**  | 商业企业、需要高稳定性的用户                     | 开发者、科研机构、教育用途                |

---

### 核心技术特征对比

| 技术方面        | **ACIS**          | **OCCT**                     |
| ----------- | ----------------- | ---------------------------- |
| **几何表示**    | 高精度 NURBS、曲面/曲线支持 | NURBS、曲面/曲线支持                |
| **拓扑结构**    | B-Rep、实体体、面、边、顶点  | B-Rep、TopoDS_Shape、Face、Edge |
| **布尔运算**    | 高鲁棒性，工业级性能        | 支持，适用于大多数应用                  |
| **几何精度**    | 精度控制优越，稳定性高       | 足够工程使用，略逊一筹                  |
| **布尔运算支持**  | 完整的布尔运算（并、交、差）    | 支持布尔操作，部分复杂模型可能失败            |
| **几何与拓扑分离** | 几何和拓扑部分有明显区分      | 几何和拓扑完全分离                    |

---

### 架构与可扩展性对比

| 维度       | **ACIS**        | **OCCT**                 |
| -------- | --------------- | ------------------------ |
| **接口风格** | 面向对象，API函数      | 完全面向对象，类层次清晰             |
| **数据结构** | 基于 ENTITY 类结构   | TopoDS_Shape 与 Geom_ 类分离 |
| **可扩展性** | 限制较少，可通过 API 扩展 | 高度可扩展，可直接修改源代码           |
| **学习曲线** | 较平滑，文档较好        | 稍陡，文档分散，但社区支持强           |

---

### 性能与鲁棒性（实际工程表现）

| 项目          | **ACIS**     | **OCCT**               |
| ----------- | ------------ | ---------------------- |
| **布尔运算成功率** | 95%+，高鲁棒性    | 70–85%，复杂模型可能失败        |
| **几何修复能力**  | 内置自动修复机制     | 通过 `ShapeFix` 修复，但较为繁琐 |
| **复杂曲面处理**  | 高鲁棒性和精度，工业稳定 | 支持，但复杂曲面可能有性能问题        |
| **大型装配支持**  | 优化良好，适用于复杂装配 | 性能较差，适用于中小规模装配         |

---

### 开发与商业应用差异

| 维度         | **ACIS**  | **OCCT**                |
| ---------- | --------- | ----------------------- |
| **成本**     | 需要付费授权    | 免费（开源）                  |
| **技术支持**   | 官方技术支持    | 社区支持+商业支持（Open Cascade） |
| **升级与兼容性** | 官方发布、稳定性高 | 开源版本更新快，可能有兼容性问题        |
| **生态系统**   | 广泛应用于商业软件 | 适用于开源项目与二次开发            |

---

### 适用场景建议

| 需求场景               | **推荐内核** |
| ------------------ | -------- |
| **科研、教学或原型开发**     | **OCCT** |
| **工业级 CAD 系统开发**   | **ACIS** |
| **需要高精度与鲁棒性的几何建模** | **ACIS** |
| **需要灵活性和开源平台的开发者** | **OCCT** |

---

## 关联映射

### 整体架构对比图

下面是两者的高层架构（概念映射）：

```
┌────────────────────────────┐           ┌────────────────────────────┐
│         ACIS Kernel        │           │         OCCT Kernel        │
├────────────────────────────┤           ├────────────────────────────┤
│  ENTITY / BODY / FACE /    │           │  TopoDS_Shape / Face /     │
│  EDGE / VERTEX (B-Rep)     │◀───▶────▶│  Edge / Vertex (B-Rep)     │
│                            │           │                            │
│  GEOMETRY (Curve/Surface)  │◀───▶────▶│  Geom_Curve / Geom_Surface │
│                            │           │                            │
│  TOPOLOGY OPERATIONS       │◀───▶────▶│  BRepBuilderAPI, BOPAlgo   │
│  (api_make_*, boolean ops) │           │  (MakeBox, Cut, Fuse, etc) │
│                            │           │                            │
│  HLR / Visualization (API) │◀───▶────▶│  HLRAlgo, AIS, V3d Viewer  │
│                            │           │                            │
│  Attributes / History /    │           │  TDF / OCAF Document       │
│  SAT/SAB Serialization     │           │  BRepTools / STEPControl   │
│                            │           │                            │
│  License: Proprietary      │           │  License: LGPL             │
└────────────────────────────┘           └────────────────────────────┘
```

> **简单理解**：
>
> * ACIS 的核心单元是 `ENTITY`（几何/拓扑对象统一接口）
> * OCCT 的核心单元是 `TopoDS_Shape`（几何和拓扑分层）
>   两者都使用 **B-Rep 表示**，但 OCCT 的几何和拓扑解耦更彻底。

---

### 模块映射表

| 功能模块     | **ACIS 类 / API**                     | **OCCT 类 / 模块**                                                | 说明          |
| :------- | :----------------------------------- | :------------------------------------------------------------- | :---------- |
| 几何点      | `SPAposition`                        | `gp_Pnt`                                                       | 三维空间点       |
| 向量       | `SPAvector`                          | `gp_Vec`                                                       | 三维向量        |
| 坐标系      | `SPAtransf`, `SPAunit_vector`        | `gp_Ax1`, `gp_Ax2`, `gp_Trsf`                                  | 坐标变换/基准     |
| 曲线       | `curve`, `api_make_curve`            | `Geom_Curve`, `Geom_BSplineCurve`                              | 支持 NURBS    |
| 曲面       | `surface`, `api_make_surface`        | `Geom_Surface`, `Geom_BSplineSurface`                          | 支持NURBS曲面   |
| 实体拓扑     | `ENTITY`, `BODY`, `FACE`, `EDGE`     | `TopoDS_Shape`, `TopoDS_Face`, `TopoDS_Edge`                   | B-Rep 拓扑结构  |
| 实体构造     | `api_make_body`, `api_make_face`     | `BRepBuilderAPI_MakeFace`, `BRepPrimAPI_MakeBox`               | 构造基础体       |
| 布尔运算     | `api_boolean`, `api_fuse`, `api_cut` | `BRepAlgoAPI_Fuse`, `BRepAlgoAPI_Cut`                          | 布尔操作        |
| 倒角/圆角    | `api_chamfer`, `api_fillet`          | `BRepFilletAPI_MakeChamfer`, `BRepFilletAPI_MakeFillet`        | 倒角与圆角       |
| HLR（隐藏线） | `api_ihl_*`                          | `HLRAlgo_Projector`, `HLRBRep_Algo`                            | 隐线计算        |
| 投影/截面    | `api_section`, `api_project`         | `BRepAlgoAPI_Section`, `GeomAPI_ProjectPointOnSurf`            | 投影与切割       |
| 拉伸/旋转    | `api_extrude`, `api_revolve`         | `BRepPrimAPI_MakePrism`, `BRepPrimAPI_MakeRevol`               | 体生成         |
| 文件导出     | `api_save_entity_list`, `SATWriter`  | `STEPControl_Writer`, `IGESControl_Writer`, `BRepTools::Write` | 文件输出        |
| 文件导入     | `api_load_entity_list`, `SATReader`  | `STEPControl_Reader`, `IGESControl_Reader`                     | 文件读取        |
| 属性系统     | `ATTRIB`, `ENTITY_ATTRIB`            | `TDF_Label`, `OCAF Document`                                   | 属性树、特征参数    |
| 可视化      | 外部 (HOOPS / ACIS Viewer)             | `AIS_InteractiveContext`, `V3d_Viewer`                         | OCCT自带可视化框架 |
| 参数容差     | `SPAresabs`, `SPAresfit`             | `Precision::Confusion()`, `BRepTools::Clean()`                 | 精度管理        |
| 数据结构导出   | `.sat/.sab`                          | `.brep/.step/.iges`                                            | 内核序列化格式     |

---

### 实体映射表

| **ACIS 类**    | **OCCT 类**             | **说明**     |
| ------------- | ---------------------- | ---------- |
| `ENTITY`      | `TopoDS_Shape`         | 统一数据接口，顶级类 |
| `BODY`        | `TopoDS_Solid`         | 实体体        |
| `FACE`        | `TopoDS_Face`          | 面          |
| `EDGE`        | `TopoDS_Edge`          | 边          |
| `VERTEX`      | `TopoDS_Vertex`        | 顶点         |
| `curve`       | `Geom_Curve`           | 几何曲线       |
| `surface`     | `Geom_Surface`         | 几何曲面       |
| `api_make_*`  | `BRepBuilderAPI_Make*` | 实体创建       |
| `api_boolean` | `BRepAlgoAPI_*`        | 布尔运算       |

---

## 最后总结

在 **ACIS** 和 **OCCT** 之间的选择，主要取决于你的**应用需求**：

* **ACIS** 适用于需要商业级支持、极高鲁棒性和优化的工业级应用；
* **OCCT** 适合开源项目、教育用途、算法研究以及希望能灵活定制和扩展的开发者。

这两者都是强大的几何建模引擎，选择合适的内核能极大提高开发效率和应用效果。

