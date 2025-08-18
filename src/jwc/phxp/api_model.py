from pydantic import BaseModel


class PhxpLabCourse(BaseModel):
    """物理实验课程条目模型"""

    SemesterID: str
    StudentID: str
    LabStatusList: str
    SeatNo: str
    CourseID: str
    CourseName: str
    TeacherID: str
    LabStatusID: str
    TeacherName: str
    Weeks: str
    WeekID: str
    TimePartID: str
    LabClassNo: str
    ClassDate: str
    UpdateDate: str
    AttendanceID: str
    AttendanceName: str
    LabElectiveEndAdvanceDays: str
    LabQuitEndAdvanceDays: str
    ElectiveStartDate: str
    ElectiveEndDate: str
    WeekName: str
    TimePartName: str
    StartTime: str
    EndTime: str
    LabName: str
    LabID: str
    Capacity: str
    ClassRoom: str
    Isquried: str
    ModuleID: str
    ModuleName: str
    Type: str
    MaximumRows: str
    StartRowIndex: str
    TotalCount: str
    ElectivedCount: str
    ElectivedNum: str


class PhxpResponse(BaseModel):
    """物理实验平台响应模型"""

    total: str
    rows: list[PhxpLabCourse]
