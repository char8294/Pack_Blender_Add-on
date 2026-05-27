# 📦 รวม Blender Add-ons (Pack Blender Add-on)

ชุดเครื่องมือเสริมสำหรับ Blender เพื่อช่วยให้การทำงาน Rigging, Modeling, และ Export สะดวกรวดเร็วยิ่งขึ้น

## 1. Advanced Symmetry Weight Mirror
*   **ชื่อไฟล์:** `advanced_symmetry_mirror.py`
*   **หมวดหมู่:** Mesh / Rigging
*   **ตำแหน่ง:** View3D > Sidebar > Skin Mirror
*   **ความสามารถ:**
    *   ใช้สำหรับ Mirror Vertex Weights (ค่าน้ำหนักกระดูก) แบบสมมาตรตามแกน X
    *   รองรับการตั้งชื่อกระดูกแบบมี Prefix (เช่น `Bip001 R ` เปลี่ยนเป็น `Bip001 L `)
    *   มีระบบ Normalize น้ำหนักอัตโนมัติ และจัดการจุดที่อยู่กึ่งกลาง (Center-line support)

## 2. Biped Names Helper
*   **ชื่อไฟล์:** `biped_names_helper.py`
*   **หมวดหมู่:** Animation / Rigging
*   **ตำแหน่ง:** View3D > Sidebar > Biped Names
*   **ความสามารถ:**
    *   ช่วยเปลี่ยนชื่อกระดูกและ Vertex Group จากรูปแบบ Biped (เช่น `... L ...`) ให้เป็นมาตรฐานของ Blender (`... .L`) ชั่วคราว
    *   ช่วยให้ใช้ฟีเจอร์ Mirror มาตรฐานของ Blender ได้ทันที
    *   สามารถกด Restore เพื่อคืนชื่อเดิมได้หลังจากแก้ไขเสร็จ

## 3. Kenji Export (Batch Better FBX)
*   **ชื่อไฟล์:** `kenji_export.py`
*   **หมวดหมู่:** Import-Export
*   **ตำแหน่ง:** View3D > Sidebar > Kenji Export
*   **ความสามารถ:**
    *   Export ไฟล์ FBX แบบกลุ่ม (Batch) โดยใช้ตัวช่วยจาก Add-on "Better FBX"
    *   สามารถกำหนด Armature หลักตัวเดียวให้พ่วงไปกับทุก Mesh ที่เลือกได้
    *   รองรับการใช้ Presets, การเลือกโฟลเดอร์ปลายทาง และการบังคับ Shade Smooth ก่อน Export

## 4. Quick Render
*   **ชื่อไฟล์:** `quick_selected_render_engine.py`
*   **หมวดหมู่:** Render
*   **ตำแหน่ง:** View3D > Sidebar > Quick Render
*   **ความสามารถ:**
    *   เรนเดอร์ภาพอย่างรวดเร็วโดยเลือกเฉพาะวัตถุที่มองเห็นใน Viewport หรือเฉพาะวัตถุที่เลือก (Selected)
    *   สลับ Render Engine (Eevee/Cycles/Workbench) ชั่วคราวเพื่อดูตัวอย่าง
    *   สามารถเรนเดอร์จากมุมมอง Viewport ได้โดยไม่ต้องมีกล้องจริงในซีน
    *   มีโหมด Batch Render Selected เพื่อแยกเรนเดอร์วัตถุทีละชิ้นเป็นคนละไฟล์

## 5. Symmetry Vertex
*   **ชื่อไฟล์:** `symmetry_vertex.py`
*   **หมวดหมู่:** Mesh / Modeling
*   **ตำแหน่ง:** Edit Mode > เมนู Mesh > Symmetry Vertex
*   **ความสามารถ:**
    *   จัดตำแหน่ง Vertex ให้สมมาตรตามแกน X, Y หรือ Z
    *   **จุดเด่น:** รองรับ "Correct Face Attributes" ทำให้ค่า UV ขยับตาม Vertex ช่วยให้ลาย Texture ไม่เบี้ยวขณะจัดความสมมาตร
    *   สามารถเลือกได้ว่าจะ Copy จากฝั่งลบไปบวก, บวกไปลบ หรือหาค่าเฉลี่ยทั้งสองฝั่ง

## 6. Clear Custom Properties (Script)
*   **ชื่อไฟล์:** `Script/clear_custom_properties.py`
*   **ประเภท:** Python Script
*   **ความสามารถ:**
    *   ลบค่า Custom Properties หรือ Metadata ทั้งหมดออกจากวัตถุที่เลือก (ทั้งระดับ Object และ Data)
    *   เหมาะสำหรับทำความสะอาดโมเดลที่ Import มาจากโปรแกรมอื่น (เช่น 3ds Max หรือ Maya) ที่มักมีค่าขยะติดมาด้วย
