import logging
import os
from typing import Annotated, Optional
import vtk, SimpleITK, sitkUtils
import slicer
from slicer.i18n import tr as _
from slicer.i18n import translate
from slicer.ScriptedLoadableModule import *
from slicer.util import VTKObservationMixin
from slicer.parameterNodeWrapper import (
    parameterNodeWrapper,
    WithinRange,
)
from slicer import vtkMRMLScalarVolumeNode, vtkMRMLMarkupsFiducialNode, vtkMRMLLabelMapVolumeNode, vtkMRMLModelNode
import numpy as np
import math

# Needle_Path_Planning
class Needle_Path_Planning(ScriptedLoadableModule):
    def __init__(self, parent):
        ScriptedLoadableModule.__init__(self, parent)
        self.parent.title = _("Path planning")  # TODO: make this more human readable by adding spaces    
        self.parent.categories = [translate("qSlicerAbstractCoreModule", "Needle Insertion Path Planning")] # TODO: set categories (folders where the module shows up in the module selector)
        self.parent.dependencies = []  # TODO: add here list of module names that this module requires
        self.parent.contributors = ["Dang The Hung (King's College London)"]  # TODO: replace with "Firstname Lastname (Organization)"     
        self.parent.helpText = _("""This is an extension to find a straight line that get to the target, at good angle, avoid and maximzing distance to obstacle, 
""") # _() function marks text as translatable to other languages
        self.parent.acknowledgementText = _("""Thank you!!!""")
#########################################################################################
        # # Additional initialization step after application startup is complete
        # slicer.app.connect("startupCompleted()", registerSampleData)

# Register sample data sets in Sample Data module. Local storage -> remove
def registerSampleData():
    """Add data sets to Sample Data module."""
    import SampleData
    iconsPath = os.path.join(os.path.dirname(__file__), "Resources/Icons")

    # To ensure that the source code repository remains small (can be downloaded and installed quickly)
    # it is recommended to store data sets that are larger than a few MB in a Github release.

    # Needle_Path_Planning1
    SampleData.SampleDataLogic.registerCustomSampleDataSource(
        # Category and sample name displayed in Sample Data module
        category="Needle_Path_Planning",
        sampleName="Needle_Path_Planning1",
        # Thumbnail should have size of approximately 260x280 pixels and stored in Resources/Icons folder.
        # It can be created by Screen Capture module, "Capture all views" option enabled, "Number of images" set to "Single".
        thumbnailFileName=os.path.join(iconsPath, "Needle_Path_Planning1.png"),
        # Download URL and target file name
        uris="https://github.com/Slicer/SlicerTestingData/releases/download/SHA256/998cb522173839c78657f4bc0ea907cea09fd04e44601f17c82ea27927937b95",
        fileNames="Needle_Path_Planning1.nrrd",
        # Checksum to ensure file integrity. Can be computed by this command:
        #  import hashlib; print(hashlib.sha256(open(filename, "rb").read()).hexdigest())
        checksums="SHA256:998cb522173839c78657f4bc0ea907cea09fd04e44601f17c82ea27927937b95",
        # This node name will be used when the data set is loaded
        nodeNames="Needle_Path_Planning1",
    )

    # Needle_Path_Planning2
    SampleData.SampleDataLogic.registerCustomSampleDataSource(
        # Category and sample name displayed in Sample Data module
        category="Needle_Path_Planning",
        sampleName="Needle_Path_Planning2",
        thumbnailFileName=os.path.join(iconsPath, "Needle_Path_Planning2.png"),
        # Download URL and target file name
        uris="https://github.com/Slicer/SlicerTestingData/releases/download/SHA256/1a64f3f422eb3d1c9b093d1a18da354b13bcf307907c66317e2463ee530b7a97",
        fileNames="Needle_Path_Planning2.nrrd",
        checksums="SHA256:1a64f3f422eb3d1c9b093d1a18da354b13bcf307907c66317e2463ee530b7a97",
        # This node name will be used when the data set is loaded
        nodeNames="Needle_Path_Planning2",
    )

# Needle_Path_PlanningParameterNode
@parameterNodeWrapper
class Needle_Path_PlanningParameterNode:
    entryPoints: vtkMRMLMarkupsFiducialNode
    targetPoints: vtkMRMLMarkupsFiducialNode
    hypothalamusLabelMap: vtkMRMLLabelMapVolumeNode
    vesselsLabelMap: vtkMRMLLabelMapVolumeNode
    ventricleLabelMap: vtkMRMLLabelMapVolumeNode
    cortexLabelMap: vtkMRMLLabelMapVolumeNode

# Needle_Path_PlanningWidget
class Needle_Path_PlanningWidget(ScriptedLoadableModuleWidget, VTKObservationMixin):
    """Uses ScriptedLoadableModuleWidget base class, available at:
    https://github.com/Slicer/Slicer/blob/main/Base/Python/slicer/ScriptedLoadableModule.py
    """

    def __init__(self, parent=None) -> None:
        """Called when the user opens the module the first time and the widget is initialized."""
        ScriptedLoadableModuleWidget.__init__(self, parent)
        VTKObservationMixin.__init__(self)  # needed for parameter node observation
        self.logic = None
        self._parameterNode = None
        self._parameterNodeGuiTag = None

    def setup(self) -> None:
        """Called when the user opens the module the first time and the widget is initialized."""
        ScriptedLoadableModuleWidget.setup(self)

        # Load widget from .ui file (created by Qt Designer).
        # Additional widgets can be instantiated manually and added to self.layout.
        uiWidget = slicer.util.loadUI(self.resourcePath("UI/Needle_Path_Planning.ui"))
        self.layout.addWidget(uiWidget)
        self.ui = slicer.util.childWidgetVariables(uiWidget)

        # Set scene in MRML widgets. Make sure that in Qt designer the top-level qMRMLWidget's
        # "mrmlSceneChanged(vtkMRMLScene*)" signal in is connected to each MRML widget's.
        # "setMRMLScene(vtkMRMLScene*)" slot.
        uiWidget.setMRMLScene(slicer.mrmlScene)

        # Create logic class. Logic implements all computations that should be possible to run
        # in batch mode, without a graphical user interface.
        self.logic = Needle_Path_PlanningLogic()

        # Connections

        # These connections ensure that we update parameter node when scene is closed
        self.addObserver(slicer.mrmlScene, slicer.mrmlScene.StartCloseEvent, self.onSceneStartClose)
        self.addObserver(slicer.mrmlScene, slicer.mrmlScene.EndCloseEvent, self.onSceneEndClose)

        # Buttons
        self.ui.dataCleaning.connect("clicked(bool)", self.dataCleaning)
        self.ui.applyButton.connect("clicked(bool)", self.onApplyButton)
        self.ui.prepareROSData.connect("clicked(bool)", self.prepareROSData)

        # Make sure parameter node is initialized (needed for module reload)
        self.initializeParameterNode()

    def cleanup(self) -> None:
        """Called when the application closes and the module widget is destroyed."""
        self.removeObservers()

    def enter(self) -> None:
        """Called each time the user opens this module."""
        # Make sure parameter node exists and observed
        self.addObserver(self._parameterNode, vtk.vtkCommand.ModifiedEvent, self._checkCanApply)
        self.initializeParameterNode()

    def exit(self) -> None:
        """Called each time the user opens a different module."""
        # Do not react to parameter node changes (GUI will be updated when the user enters into the module)
        if self._parameterNode:
            self._parameterNode.disconnectGui(self._parameterNodeGuiTag)
            self._parameterNodeGuiTag = None
            self.removeObserver(self._parameterNode, vtk.vtkCommand.ModifiedEvent, self._checkCanApply)

    def onSceneStartClose(self, caller, event) -> None:
        """Called just before the scene is closed."""
        # Parameter node will be reset, do not use it anymore
        self.setParameterNode(None)

    def onSceneEndClose(self, caller, event) -> None:
        """Called just after the scene is closed."""
        # If this module is shown while the scene is closed then recreate a new parameter node immediately
        if self.parent.isEntered:
            self.initializeParameterNode()

    def initializeParameterNode(self) -> None:
        """Ensure parameter node exists and observed."""
        # Parameter node stores all user choices in parameter values, node selections, etc.
        # so that when the scene is saved and reloaded, these settings are restored.

        self.setParameterNode(self.logic.getParameterNode())

        # Select default input nodes if nothing is selected yet to save a few clicks for the user
        if not self._parameterNode.entryPoints:
            firstVolumeNode = slicer.mrmlScene.GetFirstNodeByClass("vtkMRMLMarkupsFiducialNode")
            if firstVolumeNode:
                self._parameterNode.entryPoints = firstVolumeNode

        if not self._parameterNode.targetPoints:
            firstVolumeNode = slicer.mrmlScene.GetFirstNodeByClass("vtkMRMLMarkupsFiducialNode")
            if firstVolumeNode:
                self._parameterNode.targetPoints = firstVolumeNode

        if not self._parameterNode.hypothalamusLabelMap:
            firstVolumeNode = slicer.mrmlScene.GetFirstNodeByClass("vtkMRMLLabelMapVolumeNode")
            if firstVolumeNode:
                self._parameterNode.hypothalamusLabelMap = firstVolumeNode

        if not self._parameterNode.vesselsLabelMap:
            firstVolumeNode = slicer.mrmlScene.GetFirstNodeByClass("vtkMRMLLabelMapVolumeNode")
            if firstVolumeNode:
                self._parameterNode.vesselsLabelMap = firstVolumeNode

        if not self._parameterNode.ventricleLabelMap:
            firstVolumeNode = slicer.mrmlScene.GetFirstNodeByClass("vtkMRMLLabelMapVolumeNode")
            if firstVolumeNode:
                self._parameterNode.ventricleLabelMap = firstVolumeNode

        if not self._parameterNode.cortexLabelMap:
            firstVolumeNode = slicer.mrmlScene.GetFirstNodeByClass("vtkMRMLLabelMapVolumeNode")
            if firstVolumeNode:
                self._parameterNode.cortexLabelMap = firstVolumeNode

    def setParameterNode(self, inputParameterNode: Optional[Needle_Path_PlanningParameterNode]) -> None:
        """
        Set and observe parameter node.
        Observation is needed because when the parameter node is changed then the GUI must be updated immediately.
        """

        if self._parameterNode:
            self._parameterNode.disconnectGui(self._parameterNodeGuiTag)
            self.removeObserver(self._parameterNode, vtk.vtkCommand.ModifiedEvent, self._checkCanApply)
        self._parameterNode = inputParameterNode
        if self._parameterNode:
            # Note: in the .ui file, a Qt dynamic property called "SlicerParameterName" is set on each
            # ui element that needs connection.
            self._parameterNodeGuiTag = self._parameterNode.connectGui(self.ui)
            self.addObserver(self._parameterNode, vtk.vtkCommand.ModifiedEvent, self._checkCanApply)
            self._checkCanApply()

    def _checkCanApply(self, caller=None, event=None) -> None:
        if self._parameterNode and self._parameterNode.entryPoints and self._parameterNode.targetPoints and self._parameterNode.hypothalamusLabelMap and self._parameterNode.vesselsLabelMap and self._parameterNode.ventricleLabelMap and self._parameterNode.cortexLabelMap:
            self.ui.applyButton.toolTip = _("Compute output volume")
            self.ui.applyButton.enabled = True
        else:
            self.ui.applyButton.toolTip = _("Select input and output volume nodes")
            self.ui.applyButton.enabled = False

        if self._parameterNode and self._parameterNode.entryPoints and self._parameterNode.targetPoints:
            self.ui.dataCleaning.toolTip = _("Count the number of points and generate Models")
            self.ui.dataCleaning.enabled = True
        else:
            self.ui.dataCleaning.toolTip = _("Please select the list of points")
            self.ui.dataCleaning.enabled = False

    def dataCleaning(self) -> None:
        """Run processing when user clicks "Summarize the data and create models from label maps" button."""
        with slicer.util.tryWithErrorDisplay(_("Failed to compute results."), waitCursor=True):
            # Compute output
            self.logic.summarize_Data_and_Create_Model(self._parameterNode.entryPoints, self._parameterNode.targetPoints, True)

    def onApplyButton(self) -> None:
        """Run processing when user clicks "Apply and execute path planning" button."""
        with slicer.util.tryWithErrorDisplay(_("Failed to compute results."), waitCursor=True):
            # Compute output
            result = self.logic.process(entryPoints = self._parameterNode.entryPoints,
                                        targetPoints = self._parameterNode.targetPoints,
                                        hypothalamusLabelMap = self._parameterNode.hypothalamusLabelMap,
                                        vesselsLabelMap = self._parameterNode.vesselsLabelMap,
                                        ventricleLabelMap = self._parameterNode.ventricleLabelMap,
                                        cortexLabelMap = self._parameterNode.cortexLabelMap,
                                        cortexangleThreshold = self.ui.cortexangleThreshold.value,
                                        needleCutOffLength = self.ui.needleCutOffLength.value,
                                        printResult = True)
            # Turn the prepare ROS data button on if a Path can be found
            if (result):
                self.ui.prepareROSData.enabled = True
            else:
                self.ui.prepareROSData.enabled = False

    def prepareROSData(self) -> None:
        """Run processing when user clicks "Prepare data to send to ROS" button."""
        with slicer.util.tryWithErrorDisplay(_("Failed to prepare data for ROS."), waitCursor=True):
            # Compute output
            self.logic.create_Folder_With_Entry_and_Target_Points_and_Polydata()

# Needle_Path_PlanningLogic
class Needle_Path_PlanningLogic(ScriptedLoadableModuleLogic):
    def __init__(self) -> None:
        ScriptedLoadableModuleLogic.__init__(self)
        self.shNode = slicer.mrmlScene.GetSubjectHierarchyNode()

    def getParameterNode(self):
        return Needle_Path_PlanningParameterNode(super().getParameterNode())

    def summarize_Data_and_Create_Model(self, entryNode, targetNode, printResult: bool = True):
        """Summarize the data and create model, segmentation"""
        # Get number of entry and target point
        n_Entry = entryNode.GetNumberOfControlPoints()
        n_Target = targetNode.GetNumberOfControlPoints()
        if printResult:
            self.simple_Task_Print_Output(f"Number of entries is: {n_Entry}")
            self.simple_Task_Print_Output(f"Number of targets is: {n_Target}")
        # # Create segmentation and model from label map
        # list_of_Label_nodes = slicer.util.getNodesByClass("vtkMRMLLabelMapVolumeNode")
        # exportModelFolderItemId = self.simple_Task_Create_Folder("Models")
        # exportSegmentFolderItemId = self.simple_Task_Create_Folder("Segments")
        # for i, node in enumerate(list_of_Label_nodes):
        #     seg = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLSegmentationNode")
        #     seg.SetName("Segmentation"+node.GetName())
        #     self.shNode.SetItemParent(self.shNode.GetItemByDataNode(seg), exportSegmentFolderItemId)
        #     slicer.modules.segmentations.logic().ImportLabelmapToSegmentationNode(node, seg)
        #     slicer.modules.segmentations.logic().ExportAllSegmentsToModels(seg, exportModelFolderItemId)
        #     self.shNode.SetItemName(self.shNode.GetItemChildWithName(exportModelFolderItemId, "1"), "Model_"+ node.GetName())
        # self.shNode.SetItemParent(exportModelFolderItemId, self.shNode.GetItemParent(exportSegmentFolderItemId))
        # self.shNode.SetItemExpanded(exportSegmentFolderItemId, 0)
        return n_Entry, n_Target
        # return n_Entry, n_Target, exportModelFolderItemId, exportSegmentFolderItemId
    def check_A_Point_in_List_Is_In_A_Label_Volume_Node(self, input_point_array: np.ndarray((100,3)), label_volume_node: vtkMRMLLabelMapVolumeNode, strictly_inside_mode = True):
        """Get a list of point as np.array and a label volume node"""
        """Return a np.array(-1,) of boolean where True if a point is inside, and False if it is outside"""
        """If strictly_inside_mode is True, the function will return 1 only if 8 cubes around it is inside
        If strictly_inside_mode is False, the function will return 1 if at least 1 in 9 cubes around it is inside"""
        # Check input types
        if type(input_point_array) != np.ndarray:
            return "check_A_Point_in_List_Is_In_A_Label_Volume_Node failed: Input point need to be a np.ndarray"
        if type(label_volume_node) != vtkMRMLLabelMapVolumeNode:
            return "check_A_Point_in_List_Is_In_A_Label_Volume_Node failed: Input volume need to be a vtkMRMLLabelMapVolumeNode"
        result = np.zeros((input_point_array.shape[0],)) # Declare result vector
        label_volume_array = slicer.util.arrayFromVolume(label_volume_node).transpose() # Conver the node into np array
        # Loop through list of points, convert to IJK space, and check value of 8 cubes around it.
        spacing = np.array(label_volume_node.GetSpacing())
        rotation = vtk.vtkMatrix4x4()
        label_volume_node.GetIJKToRASDirectionMatrix(rotation)
        rotation = slicer.util.arrayFromVTKMatrix(rotation)[0:3,0:3]
        origin = np.array(label_volume_node.GetOrigin())
        for i, input_point in enumerate(input_point_array):
            x, y, z  = np.round(self.convert_RAS_to_IJK(input = input_point,
                                                        spacing = spacing, 
                                                        rotation = rotation,
                                                        origin = origin)).astype(int)
            if strictly_inside_mode:
                matrix_surround_current_point = self.get_3x3x3_Matrix_From_Bigger_Matrix_at_one_Position(x, y, z, label_volume_array) #The value of the image at x y z coordinate and 8 cubes around
                checking_value = matrix_surround_current_point[1,1,1]+matrix_surround_current_point[0,1,1]+matrix_surround_current_point[2,1,1]+matrix_surround_current_point[1,0,1]+matrix_surround_current_point[1,2,1]+matrix_surround_current_point[1,1,0]+matrix_surround_current_point[1,1,2]
                # if np.sum(matrix_surround_current_point) == 27:
                if checking_value == 7:
                    result[i] = True
            else:
                matrix_surround_current_point = self.get_2x2x2_Matrix_From_Bigger_Matrix_at_one_Position(x, y, z, label_volume_array) #The value of the image at x y z coordinate and 8 cubes around
                if np.sum(matrix_surround_current_point) == 8:
                    result[i] = True
                pass
        return result
    def check_A_Line_in_List_Is_Smaller_Than_A_Cut_Off(self, input_line_list, cut_off):
        """Get a list of lines as np.array and a cut off value"""
        """Return a np.array((-1,)) of the same length as the list.
        The Array will equal True if the vector in the list is less than a cut
        off value, and False if it is higher than a cut off value"""
        if type(input_line_list) != np.ndarray:
            return "check_A_Line_in_List_Is_Smaller_Than_A_Cut_Off failed: Input lines need to be a np.ndarray"
        result = input_line_list[:,1,:] - input_line_list[:,0,:]
        result = np.linalg.norm(result, axis=-1)
        result = result <= cut_off
        return result
    def get_Square_Distance_from_A_Line_in_List_to_A_Label_Volume_Node(self, input_line_list: np.ndarray((100,2,3)), label_volume_node: vtkMRMLLabelMapVolumeNode, discretize_distance = 1):
        """Get a list of lines as np.array and a label volume node"""
        """Return a np.array(-1,) contain the distance of each line to that model
        If they intersect the distance is 0
        If the line is outside label volume the distance return -1"""
        """The algorithm will discretize the lines with a step of discretize_distance"""
        # Check input types
        if type(input_line_list) != np.ndarray:
            return "get_Square_Distance_from_A_Line_in_List_to_A_Label_Volume_Node failed: Input lines need to be a np.ndarray"
        if type(label_volume_node) != vtkMRMLLabelMapVolumeNode:
            return "get_Square_Distance_from_A_Line_in_List_to_A_Label_Volume_Node failed: Input volume need to be a vtkMRMLLabelMapVolumeNode"
        result = np.zeros((input_line_list.shape[0],)) # Declare result vector
        # Calculate the distance matrix
        sitkInput = sitkUtils.PullVolumeFromSlicer(label_volume_node)
        distanceFilter = SimpleITK.SignedMaurerDistanceMapImageFilter()
        distanceFilter.UseImageSpacingOn()
        distanceFilter.SquaredDistanceOn()
        sitkOutput = distanceFilter.Execute(sitkInput)
        outputVolume = sitkUtils.PushVolumeToSlicer(sitkOutput, None, 'distanceMap')
        # Transform the distance volume into array
        label_volume_array = slicer.util.arrayFromVolume(outputVolume).transpose() # Conver the node into np array
        distance_max = np.max(label_volume_array)
        # Get necessary variables to convert RAS to IJK
        spacing = np.array(label_volume_node.GetSpacing())
        rotation = vtk.vtkMatrix4x4()
        label_volume_node.GetIJKToRASDirectionMatrix(rotation)
        rotation = slicer.util.arrayFromVTKMatrix(rotation)[0:3,0:3]
        origin = np.array(label_volume_node.GetOrigin())
        discretize_distance = discretize_distance / np.linalg.norm(spacing)
        # Loop through the line list
        indices_of_line_that_do_not_pass_through_label_volume = []
        for i_line_list_iterator, line  in enumerate(input_line_list):
            start_point = line[0]
            end_point = line[1]
            start_point  = self.convert_RAS_to_IJK(input = start_point,
                                                   spacing = spacing, 
                                                   rotation = rotation,
                                                   origin = origin)
            end_point    = self.convert_RAS_to_IJK(input = end_point,
                                                   spacing = spacing, 
                                                   rotation = rotation,
                                                   origin = origin)
            # Simple interator through each point on the the line
            unit_vector = end_point - start_point
            segment_length = np.linalg.norm(unit_vector)
            unit_vector = unit_vector/segment_length*discretize_distance
            number_of_segments = math.ceil(segment_length/discretize_distance)
            distance_loop = distance_max
            passing_through_label_volume = False
            for i_line_point_iterator in range(number_of_segments):
                x, y, z = np.round(start_point + unit_vector*i_line_point_iterator).astype(int)
                if (x<0) or (y<0) or (z<0) or (x>=label_volume_array.shape[0]) or (y>=label_volume_array.shape[1]) or (z>=label_volume_array.shape[2]):
                    continue
                current_distance = label_volume_array[x,y,z]
                passing_through_label_volume = True
                if current_distance < distance_loop:
                    distance_loop = current_distance
                    if current_distance<=0:
                        break
            if not(passing_through_label_volume):
                indices_of_line_that_do_not_pass_through_label_volume.append(i_line_list_iterator)
                continue    
            result[i_line_list_iterator] = distance_loop
        result[result<0] = 0
        result[indices_of_line_that_do_not_pass_through_label_volume] = -1
        slicer.mrmlScene.RemoveNode(outputVolume)
        return result
    def get_Angle_from_A_Line_in_List_to_A_Label_Volume_Node(self, input_line_list: np.ndarray((100,2,3)), label_volume_node: vtkMRMLLabelMapVolumeNode):
        """Get a list of lines as np.array and a label volume node"""
        # Check input types
        if type(input_line_list) != np.ndarray:
            return "get_Angle_from_A_Line_in_List_to_A_Label_Volume_Node failed: Input lines need to be a np.ndarray"
        """Return a np.array((-1,)) contain the angle of each line to that model
        One point of the line must be inside the model, one point must be outside
        Both are inside or both outside, return -1"""
        if type(label_volume_node) != vtkMRMLLabelMapVolumeNode:
            return "get_Angle_from_A_Line_in_List_to_A_Label_Volume_Node failed: Input volume need to be a vtkMRMLLabelMapVolumeNode"
        result = -np.ones((input_line_list.shape[0],)) # Declare result vector
        # Transform label volume to Model
        model_node = self.convert_Label_Volume_To_Model(label_node=label_volume_node)
        # Find intersection
        # Start locator - find intersection point
        tree = vtk.vtkOBBTree()
        tree.SetDataSet(model_node.GetPolyData()) 
        tree.BuildLocator()
        intersectPoints = vtk.vtkPoints()
        # Start locator - find nearest cell
        cell_locator = vtk.vtkCellLocator()
        cell_locator.SetDataSet(model_node.GetMesh())
        cell_locator.BuildLocator()
        closestPoint = [0.0, 0.0, 0.0]
        cellObj = vtk.vtkGenericCell()
        cellId = vtk.mutable(0)
        subId = vtk.mutable(0)
        dist = vtk.mutable(0.0)
        normal_vector = np.zeros((3))
        for i_line_list_iterator, line  in enumerate(input_line_list):
            start_point = line[0]
            end_point = line[1]
            tree.IntersectWithLine(start_point, end_point, intersectPoints, None)
            if intersectPoints.GetNumberOfPoints() != 1:
                continue
            intersectPoint = intersectPoints.GetPoint(0)
            # Find closest cell
            cell_locator.FindClosestPoint(intersectPoint, closestPoint, cellObj, cellId, subId, dist)
            # Calculate the normal vector
            anglecalculator = vtk.vtkTriangle()
            anglecalculator.ComputeNormalDirection(cellObj.GetPoints().GetPoint(0), cellObj.GetPoints().GetPoint(1), cellObj.GetPoints().GetPoint(2), normal_vector)
            # Calculate the angle
            angle = np.arccos(np.dot(normal_vector, end_point-start_point)/(np.linalg.norm(normal_vector)*np.linalg.norm(end_point-start_point)))
            if angle > np.pi/2:
                angle = np.pi - angle
            result[i_line_list_iterator] = angle
        slicer.mrmlScene.RemoveNode(model_node)
        return result

    def convert_IJK_to_RAS(self,
                           input: np.ndarray((3,)),
                           spacing: np.ndarray((3,)) = np.array([1,1,1]), 
                           rotation: np.ndarray((3,3)) = np.eye(3),
                           origin: np.ndarray((3,)) = np.array([0,0,0])) -> np.ndarray((3,)):
        """Order for transformation: spacing -> rotate -> translate"""
        # Check input types
        if type(input) != np.ndarray:
            return "convert_IJK_to_RAS failed: Input point need to be a np.ndarray"
        input = np.array(input).reshape(3,)
        spacing = np.array(spacing).reshape(3,)
        rotation = np.array(rotation).reshape(3,3)
        origin = np.array(origin).reshape(3,)
        return np.matmul(rotation, (input*spacing).reshape(-1,1)).reshape(-1,) + origin
    def convert_RAS_to_IJK(self,
                           input: np.ndarray((3,)),
                           spacing: np.ndarray((3,)) = np.array([1,1,1]), 
                           rotation: np.ndarray((3,3)) = np.eye(3),
                           origin: np.ndarray((3,)) = np.array([0,0,0])) -> np.ndarray((3,)):
        """Backward transformation of convert_IJK_to_RAS
        The input rotation matrix must not be singular"""
        # Check input types
        if type(input) != np.ndarray:
            return "convert_RAS_to_IJK failed: Input point need to be a np.ndarray"
        input = np.array(input).reshape(3,)
        spacing = np.array(spacing).reshape(3,)
        rotation = np.array(rotation).reshape(3,3)
        origin = np.array(origin).reshape(3,)
        try:
            return np.matmul(np.linalg.inv(rotation), (input - origin).reshape(-1,1)).reshape(-1,)/spacing
        except np.linalg.LinAlgError:
            print("Convert_RAS_to_IJK failed, the rotation matrix must be non-singular")
            return
    def get_3x3x3_Matrix_From_Bigger_Matrix_at_one_Position(self, x: int, y: int, z: int, array: np.ndarray):
        """Get 3x3x3 matrix from a bigger volume at a specific point"""
        # Check input types
        if type(array) != np.ndarray:
            return "get_3x3x3_Matrix_From_Bigger_Matrix_at_one_Position failed: Input matrix need to be a np.ndarray"
        result = np.zeros((3,3,3))
        x_upper = min(x+2, array.shape[0])
        x_lower = max(x-1, 0)

        y_upper = min(y+2, array.shape[1])
        y_lower = max(y-1, 0)
        z_upper = min(z+2, array.shape[2])
        z_lower = max(z-1, 0)
        if (x_lower>x_upper) or (y_lower>y_upper) or (z_lower>z_upper):
            return result         
        x_result_upper = min(3, array.shape[0]-x_lower)
        x_result_lower = max(0, 3-x_upper)
        y_result_upper = min(3, array.shape[1]-y_lower)
        y_result_lower = max(0, 3-y_upper)
        z_result_upper = min(3, array.shape[2]-z_lower)
        z_result_lower = max(0, 3-z_upper)
        result[x_result_lower:x_result_upper,y_result_lower:y_result_upper,z_result_lower:z_result_upper] = array[x_lower:x_upper,y_lower:y_upper,z_lower:z_upper]
        return result
    def get_2x2x2_Matrix_From_Bigger_Matrix_at_one_Position(self, x: int, y: int, z: int, array: np.ndarray):
        """Get 2x2x2 matrix from a bigger volume at a specific point"""
        # Check input types
        if type(array) != np.ndarray:
            return "get_2x2x2_Matrix_From_Bigger_Matrix_at_one_Position failed: Input matrix need to be a np.ndarray"
        result = np.zeros((2,2,2))
        x_lower = math.floor(x)
        x_upper = x_lower+2
        y_lower = math.floor(y)
        y_upper = y_lower+2
        z_lower = math.floor(z)
        z_upper = z_lower+2

        if (x_upper<0) or (y_upper<0) or (z_upper<0) or (x_lower>array.shape[0]) or (y_lower>array.shape[1]) or (z_lower>array.shape[2]):
            return result                
        x_result_upper = min(2, array.shape[0]-x_lower)
        x_result_lower = max(0, 2-x_upper)
        y_result_upper = min(2, array.shape[1]-y_lower)
        y_result_lower = max(0, 2-y_upper)
        z_result_upper = min(2, array.shape[2]-z_lower)
        z_result_lower = max(0, 2-z_upper)
        result[x_result_lower:x_result_upper,y_result_lower:y_result_upper,z_result_lower:z_result_upper] = array[x_lower:x_upper,y_lower:y_upper,z_lower:z_upper]
        return result
    def convert_Label_Volume_To_Model(self, label_node: vtkMRMLModelNode):
        seg = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLSegmentationNode")
        slicer.modules.segmentations.logic().ImportLabelmapToSegmentationNode(label_node, seg)
        self.shNode = slicer.mrmlScene.GetSubjectHierarchyNode()
        folder_ID = self.shNode.CreateFolderItem(self.shNode.GetSceneItemID(), "Subfolder")
        slicer.modules.segmentations.logic().ExportAllSegmentsToModels(seg, folder_ID)
        idlist = vtk.vtkIdList()
        self.shNode.GetItemChildren(folder_ID,idlist)
        modelID = idlist.GetId(0)
        slicer.mrmlScene.RemoveNode(seg)
        model_node = self.shNode.GetItemDataNode(modelID)
        model_node.SetName(str(np.random.random()))
        self.shNode.SetItemParent(modelID, self.shNode.GetSceneItemID())
        self.shNode.RemoveItem(folder_ID)
        return model_node

    def process(self,
                entryPoints: vtkMRMLMarkupsFiducialNode,
                targetPoints: vtkMRMLMarkupsFiducialNode,
                hypothalamusLabelMap: vtkMRMLLabelMapVolumeNode,
                vesselsLabelMap: vtkMRMLLabelMapVolumeNode,
                ventricleLabelMap: vtkMRMLLabelMapVolumeNode,
                cortexLabelMap: vtkMRMLLabelMapVolumeNode,
                cortexangleThreshold: float = 55,
                needleCutOffLength: float = 60,
                printResult: bool = True) -> None:
        """
        Run the processing algorithm.
        entryPoints: list of potential entry points,
        targetPoints: list of potential target points,
        hypothalamusLabelMap: go into hypothalamus,
        vesselsLabelMap: avoid vessels and maximize its distance,
        ventricleLabelMap: avoid ventricle,
        cortexLabelMap: find path that have angle < threshold,
        cortexangleThreshold: threshold for angle of the line to cortex
        """
        import time
        logging.info(f"Processing started")
        startTime = time.time()
        ### Main code
        # Turn point to array
        entryPoints = slicer.util.arrayFromMarkupsControlPoints(entryPoints)
        targetPoints = slicer.util.arrayFromMarkupsControlPoints(targetPoints)

        # Early stop if no point are input
        if len(entryPoints) == 0 or len(targetPoints) == 0 :
            stopTime = time.time()
            self.simple_Task_Print_Output(f"Processing completed in {stopTime-startTime:.2f} seconds\nNo path satisfied the conditions!!!", printResult)
            return False
        # Check if the target get into hypothalamus
        list_of_inside_points = self.check_A_Point_in_List_Is_In_A_Label_Volume_Node(input_point_array=targetPoints,label_volume_node=hypothalamusLabelMap, strictly_inside_mode=False)
        # Filter the remaining target points that is inside
        targetPoints = targetPoints[list_of_inside_points==True]
        # Early stop if it can't satisfy the conditions
        if len(targetPoints) == 0:
            stopTime = time.time()
            self.simple_Task_Print_Output(f"Processing completed in {stopTime-startTime:.2f} seconds\nNo path satisfied the conditions!!!", printResult)
            return False
        # Construct a list of line by a combination of start points and end points
        list_of_line = []
        for entryPoint in entryPoints:
            for targetPoint in targetPoints:
                list_of_line.append([entryPoint,targetPoint])
        list_of_line = np.array(list_of_line)

        # Check if the lines meet the length requirement
        check_lines_length = self.check_A_Line_in_List_Is_Smaller_Than_A_Cut_Off(list_of_line, needleCutOffLength)
        list_of_line = list_of_line[check_lines_length]
        # Early stop if it can't satisfy the conditions
        if len(list_of_line) == 0:
            stopTime = time.time()
            self.simple_Task_Print_Output(f"Processing completed in {stopTime-startTime:.2f} seconds\nNo path satisfied the conditions!!!", printResult)
            return False
        
        # Find the angle of lines
        angles_to_cortex = self.get_Angle_from_A_Line_in_List_to_A_Label_Volume_Node(input_line_list=list_of_line, label_volume_node=cortexLabelMap)
        # Filter the lines meeting the angle condition
        angles_to_cortex = angles_to_cortex*180/np.pi
        list_of_line = list_of_line[angles_to_cortex<cortexangleThreshold]
        angles_to_cortex = angles_to_cortex[angles_to_cortex<cortexangleThreshold]
        list_of_line = list_of_line[angles_to_cortex>0]
        angles_to_cortex = angles_to_cortex[angles_to_cortex>0]
        # Early stop if it can't satisfy the conditions
        if len(list_of_line) == 0:
            stopTime = time.time()
            self.simple_Task_Print_Output(f"Processing completed in {stopTime-startTime:.2f} seconds\nNo path satisfied the conditions!!!", printResult)
            return False
        
        # Finding the distance to vessels
        distance_to_vessels = self.get_Square_Distance_from_A_Line_in_List_to_A_Label_Volume_Node(input_line_list=list_of_line, label_volume_node=vesselsLabelMap, discretize_distance=1)
        # Filter the remaining lines do not intersect inside
        list_of_line = list_of_line[distance_to_vessels!=0]
        angles_to_cortex = angles_to_cortex[distance_to_vessels!=0]
        distance_to_vessels = distance_to_vessels[distance_to_vessels!=0]
        # Early stop if it can't satisfy the conditions
        if len(list_of_line) == 0:
            stopTime = time.time()
            self.simple_Task_Print_Output(f"Processing completed in {stopTime-startTime:.2f} seconds\nNo path satisfied the conditions!!!", printResult)
            return False
        
        # Finding the distance to ventricle
        distance_to_ventricles = self.get_Square_Distance_from_A_Line_in_List_to_A_Label_Volume_Node(input_line_list=list_of_line, label_volume_node=ventricleLabelMap, discretize_distance=1)
        # Filter the remaining lines do not intersect inside
        list_of_line = list_of_line[distance_to_ventricles!=0]
        distance_to_vessels = distance_to_vessels[distance_to_ventricles!=0]
        angles_to_cortex = angles_to_cortex[distance_to_ventricles!=0]
        distance_to_ventricles = distance_to_ventricles[distance_to_ventricles!=0]
        # Early stop if it can't satisfy the conditions
        if len(list_of_line) == 0:
            stopTime = time.time()
            self.simple_Task_Print_Output(f"Processing completed in {stopTime-startTime:.2f} seconds\nNo path satisfied the conditions!!!", printResult)
            return False
        
        stopTime = time.time()
        # Find the best line
        sorted_indices = np.argsort(-distance_to_vessels)
        # # Get 10 best lines uncomment to print number_of_line_to_get satisfied lines
        # number_of_line_to_get = 10
        # print(f"Best {number_of_line_to_get} lines: \n {list_of_line[sorted_indices[:number_of_line_to_get]]}")
        # print(f"Angles: {angles_to_cortex[sorted_indices[:number_of_line_to_get]]}")
        # print(f"Square distances: {distance_to_vessels[sorted_indices[:number_of_line_to_get]]}")

        # Get best_line
        best_line = list_of_line[sorted_indices[0]]
        start_point = best_line[0]
        end_point = best_line[1]
        if printResult:            
            # Visualize the best lines
            qualified_line = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLMarkupsLineNode")
            qualified_line.SetName(f"Best | Angle: {round(angles_to_cortex[sorted_indices[0]])} | Distance: {round(np.sqrt(distance_to_vessels[sorted_indices[0]]))} | Length: {round(np.linalg.norm(end_point-start_point))}")            
            qualified_line.SetLineStartPosition(start_point)
            qualified_line.SetLineEndPosition(end_point)
            qualified_line.GetDisplayNode().SetPropertiesLabelVisibility(0)
            # Show info of best line
            self.simple_Task_Print_Output(f"Processing completed in {stopTime-startTime:.2f} seconds", printResult)
            self.simple_Task_Print_Output(f"Number of qualified lines: {list_of_line.shape[0]}", printResult)
            self.simple_Task_Print_Output(f"Coordinate of best entry point: {start_point}", printResult)
            self.simple_Task_Print_Output(f"Coordinate of best target point: {end_point}", printResult)
            self.simple_Task_Print_Output(f"Characteristics of best line:", printResult)
            self.simple_Task_Print_Output(f"Angle to Cortex: {round(angles_to_cortex[sorted_indices[0]])} degree", printResult)
            self.simple_Task_Print_Output(f"Distance to Vessel: {round(np.sqrt(distance_to_vessels[sorted_indices[0]]))} mm", printResult)
            self.simple_Task_Print_Output(f"Length of path: {round(np.linalg.norm(end_point-start_point))} mm", printResult)

        # Store data so they could be prepare to send to ROS later
        self.start_point_for_ROS = start_point
        self.end_point_for_ROS = end_point
        self.hypothalamusLabelMapfor_ROS = hypothalamusLabelMap
        self.vesselsLabelMapfor_ROS = vesselsLabelMap
        self.ventricleLabelMapfor_ROS = ventricleLabelMap
        self.cortexLabelMapfor_ROS = cortexLabelMap
        return True

    def create_Folder_With_Entry_and_Target_Points_and_Polydata(self) -> None:
        """
        Create a folder with:
        vtkMRMLMarkupsFiducialNode where the entry point and target point are named correctly to send to ROS
        vtkMRMLModelNode where brain models are stored to send to ROS
        vtkMRMLModelNode where a test model are stored to send to ROS for orietation checking

        """
        # Create a folder to hold ROS data
        self.DataToSendToROSfolder_ID = self.simple_Task_Create_Folder("DataToSendToROS")
        # Create vtkMRMLMarkupsFiducialNode and add 2 points
        points = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLMarkupsFiducialNode", "ROS_entry_and_target_points")
        points.AddControlPoint(self.start_point_for_ROS, "entry_point")
        points.AddControlPoint(self.end_point_for_ROS, "target_point")
        # Create Brain model for ROS
        hypothalamusModel = self.convert_Label_Volume_To_Model(self.hypothalamusLabelMapfor_ROS)
        hypothalamusModel.SetName("ROShypothalamusModel")
        vesselsModel = self.convert_Label_Volume_To_Model(self.vesselsLabelMapfor_ROS)
        vesselsModel.SetName("ROSvesselsModel")
        ventricleModel = self.convert_Label_Volume_To_Model(self.ventricleLabelMapfor_ROS)
        ventricleModel.SetName("ROSventricleModel")
        cortexModel = self.convert_Label_Volume_To_Model(self.cortexLabelMapfor_ROS)
        cortexModel.SetName("ROScortexModel")
        # Move the data to ROS folder
        self.shNode.SetItemParent(self.shNode.GetItemByDataNode(points), self.DataToSendToROSfolder_ID)
        self.shNode.SetItemParent(self.shNode.GetItemByDataNode(hypothalamusModel), self.DataToSendToROSfolder_ID)
        self.shNode.SetItemParent(self.shNode.GetItemByDataNode(vesselsModel), self.DataToSendToROSfolder_ID)
        self.shNode.SetItemParent(self.shNode.GetItemByDataNode(ventricleModel), self.DataToSendToROSfolder_ID)
        self.shNode.SetItemParent(self.shNode.GetItemByDataNode(cortexModel), self.DataToSendToROSfolder_ID)
        # Add a left hand model to send to ROS for checking orientation (checking your sanity!!!)
        testDataPath = os.path.join(os.path.dirname(__file__), "Testing/Python/Data/")
        orientationValidationModel = slicer.util.loadModel(testDataPath + "ROS_orientation_validation_model.obj")
        orientationValidationModel.SetName("ROSorientationValidationModel")
        self.shNode.SetItemParent(self.shNode.GetItemByDataNode(orientationValidationModel), self.DataToSendToROSfolder_ID)
        # Make the folder visible
        pluginHandler = slicer.qSlicerSubjectHierarchyPluginHandler().instance()
        volPlugin = pluginHandler.getOwnerPluginForSubjectHierarchyItem(self.DataToSendToROSfolder_ID)
        volPlugin.setDisplayVisibility(self.DataToSendToROSfolder_ID, 1)

    def simple_Task_Create_Folder(self, folder_name):
        """Create a folder and collapse it"""
        self.shNode = slicer.mrmlScene.GetSubjectHierarchyNode()
        folder_ID = self.shNode.CreateFolderItem(self.shNode.GetSceneItemID(), folder_name)
        # Collapse the folder
        self.shNode.SetItemExpanded(folder_ID, 0)
        # Hide the folder
        pluginHandler = slicer.qSlicerSubjectHierarchyPluginHandler().instance()
        volPlugin = pluginHandler.getOwnerPluginForSubjectHierarchyItem(folder_ID)
        volPlugin.setDisplayVisibility(folder_ID, 0)
        return folder_ID
    def simple_Task_Print_Output(self, text, printResult: bool = True):
        """Logging and Printing something to the console"""
        if printResult:
            logging.info(text)
            print(text)

# Needle_Path_PlanningTest
class Needle_Path_PlanningTest(ScriptedLoadableModuleTest):
    def setUp(self):
        """Do whatever is needed to reset the state - typically a scene clear will be enough."""
        # Clear
        self.shNode = slicer.mrmlScene.GetSubjectHierarchyNode()
        self.shNode.RemoveAllItems()
        slicer.mrmlScene.RemoveNode(slicer.mrmlScene.RemoveNode(self.shNode))
        # Restart
        slicer.mrmlScene.Clear()
        # Declare variable to control system
        self.shNode = slicer.mrmlScene.GetSubjectHierarchyNode()
        self.logic = Needle_Path_PlanningLogic()
        #Path to place that store data
        # self.test_data_folder_path = "D:/Code/3D_slicer/Navigation_robotics/Data/Week_2_4_TestSet_Path_planning/" #This Path is on my local computer
        testDataPath = os.path.join(os.path.dirname(__file__), "Testing/Python/Data/")
        self.test_data_folder_path = testDataPath # Change this into the path that store the test data on your computer if you can't download whole code with test data
        # Create my custom logger
        logging_level = logging.INFO #Choose your logging level
        self.logger_custom = logging.getLogger("My_test_logger")
        self.logger_custom.handlers = []
        self.logger_custom.filters = []
        self.logger_custom.setLevel(logging_level)
        # # Create a file handler to log messages to a file
        file_handler = logging.StreamHandler()
        file_handler.setLevel(logging_level)
        self.logger_custom.addHandler(file_handler)
        # Declare folder for saving test model
        self.volumefortestfolderID = self.simple_Task_Create_Folder("VolumeForTest")
        self.labelvolumefortestfolderID = self.simple_Task_Create_Folder("LabelVolumeForTest")
        self.segmentationfortestfolderID = self.simple_Task_Create_Folder("SegmentationForTest")
        self.modelfortestfolderID = self.simple_Task_Create_Folder("ModelForTest")
    def runTest(self):
        """Run as few or as many tests as needed here."""
        self.setUp()
        self.load_Data()
        # Creating common test objects
        self.test_standard_volume, self.test_standard_label_volume, self.test_standard_segmentation, self.test_standard_model = self.object_Creation_For_Testing_Creating_Box_All(nodeNameEnd = "Standard",
                                                            imageSize = [16, 64, 32],
                                                            imageOrigin = [1.0, 1.0, 0.0],
                                                            imageSpacing = [2.0, 2.0, 2.0],
                                                            imageDirections = [[np.cos(np.pi/4),-np.sin(np.pi/4),0], [np.sin(np.pi/4),np.cos(np.pi/4),0], [0,0,1]],
                                                            boxEdgeLength = [8,32,16])

        # self.object_Creation_For_Testing_Creating_Box_Volume("Volume")
        # self.object_Creation_For_Testing_Creating_Box_Label_Volume("Label")
        # self.object_Creation_For_Testing_Creating_Box_Segmentation("Segmentation")
        # self.object_Creation_For_Testing_Creating_Box_Model("Model")

        # Run different tests
        self.unit_test_convert_IJK_to_RAS()
        self.unit_test_convert_RAS_tos_IJK()
        self.unit_test_get_3x3x3_Matrix_From_Bigger_Matrix_at_one_Position()
        self.unit_test_get_2x2x2_Matrix_From_Bigger_Matrix_at_one_Position()
        self.unit_test_convert_Label_Volume_To_Model()

        self.test_summarize_Data_and_Create_Model()
        self.test_check_A_Point_in_List_Is_In_A_Label_Volume_Node()
        self.test_check_A_Line_in_List_Is_Smaller_Than_A_Cut_Off()
        self.test_get_Distance_from_A_Line_in_List_to_A_Label_Volume_Node()
        self.test_get_Angle_from_A_Line_in_List_to_A_Label_Volume_Node()

        self.test_Integrated_Code()

        # Remove test object
        self.shNode.RemoveItem(self.volumefortestfolderID)
        self.shNode.RemoveItem(self.labelvolumefortestfolderID)
        self.shNode.RemoveItem(self.segmentationfortestfolderID)
        self.shNode.RemoveItem(self.modelfortestfolderID)
        
    def load_Data(self):
        """Load data and set their visual"""
        # Load test data
        self.start_points = slicer.util.loadMarkups(self.test_data_folder_path + "entriesSubsample.fcsv")
        self.end_points = slicer.util.loadMarkups(self.test_data_folder_path+"targetsSubsample.fcsv")
        self.cortex_label_map = slicer.util.loadLabelVolume(self.test_data_folder_path+"r_cortexTest.nii.gz")
        self.hypothalamus_label_map = slicer.util.loadLabelVolume(self.test_data_folder_path+"r_hippoTest.nii.gz")
        self.ventricle_label_map = slicer.util.loadLabelVolume(self.test_data_folder_path+"ventriclesTest.nii.gz")
        self.vessel_label_map = slicer.util.loadLabelVolume(self.test_data_folder_path+"vesselsTestDilate1.nii.gz")
        self.general_volume = slicer.util.loadVolume(self.test_data_folder_path+"fakeBrainTest.nii.gz")
        # Hide the nodes
        pluginHandler = slicer.qSlicerSubjectHierarchyPluginHandler().instance()
        volItem = self.shNode.GetItemByDataNode(self.general_volume)
        volPlugin = pluginHandler.getOwnerPluginForSubjectHierarchyItem(volItem)
        volPlugin.setDisplayVisibility(volItem, 0)
        volItem = self.shNode.GetItemByDataNode(self.vessel_label_map)
        volPlugin = pluginHandler.getOwnerPluginForSubjectHierarchyItem(volItem)
        volPlugin.setDisplayVisibility(volItem, 0)
        self.start_points.GetDisplayNode().SetVisibility(0)
        self.end_points.GetDisplayNode().SetVisibility(0)
    def test_summarize_Data_and_Create_Model(self):
        """Test summarize_Data_and_Create_Model function"""
        successful_tested = 1
        # n_Entry, n_Target, exportModelFolderItemId, exportSegmentFolderItemId = self.logic.summarize_Data_and_Create_Model(self.start_points, self.end_points)
        n_Entry, n_Target= self.logic.summarize_Data_and_Create_Model(self.start_points, self.end_points, False)
        successful_tested = not(n_Entry != 48 or n_Target != 21)
        # self.shNode.RemoveItem(exportModelFolderItemId, True, True)
        # self.shNode.RemoveItem(exportSegmentFolderItemId, True, True)
        self.simple_Task_Logging_Test_Outcome("Summarize number of entry points and target points", successful_tested)
    def test_check_A_Point_in_List_Is_In_A_Label_Volume_Node(self):
        """Test check_A_Point_in_List_Is_In_A_Label_Volume_Node function"""
        successful_tested = 1
        ### Example 1 - Positive, negative, and border case
        # Create a label volume node and point
        label_volume_node = self.test_standard_label_volume
        input_point = np.array([[1,1,0], [0,16.5,16.5], [10,0,16], [0,25,10]])
        expected_result = np.array([True, True, False, False])
        result = self.logic.check_A_Point_in_List_Is_In_A_Label_Volume_Node(input_point, label_volume_node, strictly_inside_mode=False)
        # Check
        if np.linalg.norm(result - expected_result) > 0.001:
            successful_tested = 0        
        ### Example 2 - test the borderline point when strictly_inside_mode=True
        # Create a label volume node and point
        label_volume_node = self.test_standard_label_volume
        input_point = np.array([[1,1,0], [0,16.5,16.5], [10,0,16]])
        expected_result = np.array([False, True, False])
        result = self.logic.check_A_Point_in_List_Is_In_A_Label_Volume_Node(input_point, label_volume_node, strictly_inside_mode=True)
        # Check
        if np.linalg.norm(result - expected_result) > 0.001:
            successful_tested = 0        
        ### Example 3 - Null case
        # Create a label volume node and point
        label_volume_node = self.test_standard_label_volume
        input_point = None
        expected_result = "check_A_Point_in_List_Is_In_A_Label_Volume_Node failed: Input point need to be a np.ndarray"
        result = self.logic.check_A_Point_in_List_Is_In_A_Label_Volume_Node(input_point, label_volume_node)
        # Check
        if expected_result != result:
            successful_tested = 0
        ### Example 4 - Null case
        # Create a label volume node and point
        label_volume_node = None
        input_point = np.array([0,0,0])
        expected_result = "check_A_Point_in_List_Is_In_A_Label_Volume_Node failed: Input volume need to be a vtkMRMLLabelMapVolumeNode"
        result = self.logic.check_A_Point_in_List_Is_In_A_Label_Volume_Node(input_point, label_volume_node)
        # Check
        if expected_result != result:
            successful_tested = 0
        
        # Log the result
        self.simple_Task_Logging_Test_Outcome("Check a Point in List is in a Label Volume Node", successful_tested)
    def test_check_A_Line_in_List_Is_Smaller_Than_A_Cut_Off(self):
        """Test check_A_Line_in_List_Is_Smaller_Than_A_Cut_Off function"""
        successful_tested = 1
        ### Example 1 - Null case
        # Create a line list and cut off
        input_line_list = None
        cut_off = 60
        expected_result = "check_A_Line_in_List_Is_Smaller_Than_A_Cut_Off failed: Input lines need to be a np.ndarray"
        result = self.logic.check_A_Line_in_List_Is_Smaller_Than_A_Cut_Off(input_line_list, cut_off)
        # Check
        if expected_result != result:
            successful_tested = 0
        ### Example 2 - Positive, negative, and border case
        # Create a line list and cut off
        input_line_list = np.array([[[0,0,0], [0,0,60]],
                                    [[0,60,0], [0,0,0]],
                                    [[61,0,0], [0,0,0]],
                                    [[0,0,0], [34,34,34]],
                                    [[0,0,0], [35,35,35]]])
        cut_off = 60
        expected_result = np.array([True, True, False, True, False])
        result = self.logic.check_A_Line_in_List_Is_Smaller_Than_A_Cut_Off(input_line_list, cut_off)
        # Check
        if np.any((result == expected_result) == False):
            successful_tested = 0        
        self.simple_Task_Logging_Test_Outcome("Check A Line in List Is Smaller Than A Cut Off", successful_tested)
    def test_get_Distance_from_A_Line_in_List_to_A_Label_Volume_Node(self):
        """Test get_Distance_from_A_Line_in_List_to_A_Label_Volume_Node function"""
        successful_tested = 1
        ### Example 1 - Null case
        # Create a label volume node and point
        label_volume_node = self.test_standard_label_volume
        input_line_list = None
        expected_result = "get_Square_Distance_from_A_Line_in_List_to_A_Label_Volume_Node failed: Input lines need to be a np.ndarray"
        result = self.logic.get_Square_Distance_from_A_Line_in_List_to_A_Label_Volume_Node(input_line_list, label_volume_node)
        # Check
        if expected_result != result:
            successful_tested = 0
        ### Example 2 - Null case
        # Create a label volume node and point
        label_volume_node = None
        input_line_list = np.array([0,0,0])
        expected_result = "get_Square_Distance_from_A_Line_in_List_to_A_Label_Volume_Node failed: Input volume need to be a vtkMRMLLabelMapVolumeNode"
        result = self.logic.get_Square_Distance_from_A_Line_in_List_to_A_Label_Volume_Node(input_line_list, label_volume_node)
        # Check
        if expected_result != result:
            successful_tested = 0
        ### Example 3 - one line is outside label volume-> return -1 for that line
        # Create a label volume node and point
        label_volume_node = self.test_standard_label_volume
        input_line_list = np.array([[[1,1,1], [-1,-1,-1]],
                                    [[3,1,2], [6,3,2]],
                                    [[3,1,2], [1,2,2]]])
        expected_result = np.array([0, -1, 0])
        result = self.logic.get_Square_Distance_from_A_Line_in_List_to_A_Label_Volume_Node(input_line_list, label_volume_node)
        # Check
        if np.linalg.norm(result - expected_result) > 0.001:
            successful_tested = 0        
        ### Example 4
        # Create a label volume node and point
        label_volume_node = self.test_standard_label_volume
        input_line_list = np.array([[[1,1,1], [-1,-1,-1]],
                                    [[3,3,36], [5,6,100]],
                                    [[3,1,2], [1,2,2]]])
        expected_result = np.array([0, 36, 0])
        result = self.logic.get_Square_Distance_from_A_Line_in_List_to_A_Label_Volume_Node(input_line_list, label_volume_node)
        # Check
        if np.linalg.norm(result - expected_result) > 0.001:
            successful_tested = 0        
        # Log the result
        self.simple_Task_Logging_Test_Outcome("Get Distance from a Line in List to a Label Volume Node", successful_tested)
    def test_get_Angle_from_A_Line_in_List_to_A_Label_Volume_Node(self):
        """Test get_Angle_from_A_Line_in_List_to_A_Label_Volume_Node function"""
        successful_tested = 1
        ### Example 1
        # Create a label volume node and point
        label_volume_node = self.test_standard_label_volume
        input_line_list = None
        expected_result = "get_Angle_from_A_Line_in_List_to_A_Label_Volume_Node failed: Input lines need to be a np.ndarray"
        result = self.logic.get_Angle_from_A_Line_in_List_to_A_Label_Volume_Node(input_line_list, label_volume_node)
        # Check
        if expected_result != result:
            successful_tested = 0
        ### Example 2
        # Create a label volume node and point
        label_volume_node = None
        input_line_list = np.array([0,0,0])
        expected_result = "get_Angle_from_A_Line_in_List_to_A_Label_Volume_Node failed: Input volume need to be a vtkMRMLLabelMapVolumeNode"
        result = self.logic.get_Angle_from_A_Line_in_List_to_A_Label_Volume_Node(input_line_list, label_volume_node)
        # Check
        if expected_result != result:
            successful_tested = 0
        ### Example 3 - one line is outside label volume-> return -1 for that line
        # Create a label volume node and point
        label_volume_node = self.test_standard_label_volume
        input_line_list = np.array([[[0,50,5], [0,5,5]],
                                    [[0,10,15], [-10,0,15]],
                                    [[0,5,100], [0,5,-10]],
                                    [[0,10,10], [0,5,5]]])
        expected_result = np.array([np.pi/4, 0, -1, -1])
        result = self.logic.get_Angle_from_A_Line_in_List_to_A_Label_Volume_Node(input_line_list, label_volume_node)
        # Check
        if np.linalg.norm(result - expected_result) > 0.05:
            successful_tested = 0        
        self.simple_Task_Logging_Test_Outcome("Get Angle from a Line in List to a Label Volume Node", successful_tested)

    def test_Integrated_Code(self):
        """Test integrated code with test dataset. The label node are mixed together"""
        successful_tested = 1
        ### Example 1
        # Propper input
        expected_result = True
        result = self.logic.process(entryPoints = self.start_points,
                                    targetPoints = self.end_points,
                                    hypothalamusLabelMap = self.hypothalamus_label_map,
                                    vesselsLabelMap = self.vessel_label_map,
                                    ventricleLabelMap = self.ventricle_label_map,
                                    cortexLabelMap = self.cortex_label_map,
                                    cortexangleThreshold = 55,
                                    needleCutOffLength = 60,
                                    printResult = False)
        # Check
        if expected_result != result:
            successful_tested = 0
        ### Example 2
        # Change entry and target point
        expected_result = False
        result = self.logic.process(entryPoints = self.end_points, ####
                                    targetPoints = self.start_points, ####
                                    hypothalamusLabelMap = self.hypothalamus_label_map,
                                    vesselsLabelMap = self.vessel_label_map,
                                    ventricleLabelMap = self.ventricle_label_map,
                                    cortexLabelMap = self.cortex_label_map,
                                    cortexangleThreshold = 55,
                                    needleCutOffLength = 60,
                                    printResult = False)
        # Check
        if expected_result != result:
            successful_tested = 0
        ### Example 3
        # Put cortext into vessel 
        expected_result = False
        result = self.logic.process(entryPoints = self.start_points,
                                    targetPoints = self.end_points,
                                    hypothalamusLabelMap = self.hypothalamus_label_map,
                                    vesselsLabelMap = self.cortex_label_map, ####
                                    ventricleLabelMap = self.ventricle_label_map, 
                                    cortexLabelMap = self.cortex_label_map,
                                    cortexangleThreshold = 55,
                                    needleCutOffLength = 60,
                                    printResult = False)
        # Check
        if expected_result != result:
            successful_tested = 0
        ### Example 4
        # Put cortext into ventricle
        expected_result = False
        result = self.logic.process(entryPoints = self.start_points,
                                    targetPoints = self.end_points,
                                    hypothalamusLabelMap = self.hypothalamus_label_map,
                                    vesselsLabelMap = self.vessel_label_map,
                                    ventricleLabelMap = self.cortex_label_map, ####
                                    cortexLabelMap = self.cortex_label_map,
                                    cortexangleThreshold = 55,
                                    needleCutOffLength = 60,
                                    printResult = False)
        # Check
        if expected_result != result:
            successful_tested = 0
        ### Example 5
        # Reduce threshhold for angle
        expected_result = False
        result = self.logic.process(entryPoints = self.start_points,
                                    targetPoints = self.end_points,
                                    hypothalamusLabelMap = self.hypothalamus_label_map,
                                    vesselsLabelMap = self.vessel_label_map,
                                    ventricleLabelMap = self.ventricle_label_map,
                                    cortexLabelMap = self.cortex_label_map,
                                    cortexangleThreshold = 5, ####
                                    needleCutOffLength = 60,
                                    printResult = False)
        # Check
        if expected_result != result:
            successful_tested = 0
        ### Example 6
        # Reduce threshhold for path length
        expected_result = False
        result = self.logic.process(entryPoints = self.start_points,
                                    targetPoints = self.end_points,
                                    hypothalamusLabelMap = self.hypothalamus_label_map,
                                    vesselsLabelMap = self.vessel_label_map,
                                    ventricleLabelMap = self.ventricle_label_map,
                                    cortexLabelMap = self.cortex_label_map,
                                    cortexangleThreshold = 55, ####
                                    needleCutOffLength = 40,
                                    printResult = False)
        # Check
        if expected_result != result:
            successful_tested = 0
        ### Example 7
        # Put hyppothalamus into vessel
        expected_result = False
        result = self.logic.process(entryPoints = self.start_points,
                                    targetPoints = self.end_points,
                                    hypothalamusLabelMap = self.hypothalamus_label_map,
                                    vesselsLabelMap = self.hypothalamus_label_map, ####
                                    ventricleLabelMap = self.ventricle_label_map,
                                    cortexLabelMap = self.cortex_label_map,
                                    cortexangleThreshold = 55,
                                    needleCutOffLength = 60,
                                    printResult = False)
        # Check
        if expected_result != result:
            successful_tested = 0
        self.simple_Task_Logging_Test_Outcome("All system test - No unwanted behaviors", successful_tested)

    def unit_test_convert_IJK_to_RAS(self):
        """Test convert_IJK_to_RAS function"""
        successful_tested = 1
        # Example 1
        original_vector = np.array([0,0,0])
        expected_result_vector = np.array([0,0,0])
        result_vector = self.logic.convert_IJK_to_RAS(input = original_vector,
                                                      spacing = np.array([1,1,1]),
                                                      rotation = np.eye(3),
                                                      origin = np.array([0,0,0]))
        if np.linalg.norm(result_vector-expected_result_vector) > 0.001:
            successful_tested = 0
        # Example 2
        original_vector = np.array([1,0,0])
        expected_result_vector = np.array([0,10,0])
        result_vector = self.logic.convert_IJK_to_RAS(input = original_vector,
                                                      spacing = np.array([5,5,5]),
                                                      rotation = np.array([[0,-1,0],[1,0,0],[0,0,1]]),
                                                      origin = np.array([0,5,0]))
        if np.linalg.norm(result_vector-expected_result_vector) > 0.001:
            successful_tested = 0
        # Example 3
        original_vector = None
        expected_result_vector = "convert_IJK_to_RAS failed: Input point need to be a np.ndarray"
        result_vector = self.logic.convert_IJK_to_RAS(input = original_vector,
                                                      spacing = np.array([5,5,5]),
                                                      rotation = np.array([[0,-1,0],[1,0,0],[0,0,1]]),
                                                      origin = np.array([0,5,0]))
        if result_vector != expected_result_vector:
            successful_tested = 0
        self.simple_Task_Logging_Unit_Test_Outcome("Convert IJK to RAS", successful_tested)
    def unit_test_convert_RAS_tos_IJK(self):
        """Test convert_RAS_tos_IJK function"""
        successful_tested = 1
        # Example 1
        original_vector = np.array([0,0,0])
        expected_result_vector = np.array([0,0,0])
        result_vector = self.logic.convert_RAS_to_IJK(input = original_vector,
                                                      spacing = np.array([1,1,1]),
                                                      rotation = np.eye(3),
                                                      origin = np.array([0,0,0]))
        if np.linalg.norm(result_vector-expected_result_vector) > 0.001:
            successful_tested = 0
        # Example 2
        original_vector = np.array([0,10,0])
        expected_result_vector = np.array([1,0,0])
        result_vector = self.logic.convert_RAS_to_IJK(input = original_vector,
                                                      spacing = np.array([5,5,5]),
                                                      rotation = np.array([[0,-1,0],[1,0,0],[0,0,1]]),
                                                      origin = np.array([0,5,0]))
        if np.linalg.norm(result_vector-expected_result_vector) > 0.001:
            successful_tested = 0
        # Example 3
        original_vector = None
        expected_result_vector = "convert_RAS_to_IJK failed: Input point need to be a np.ndarray"
        result_vector = self.logic.convert_RAS_to_IJK(input = original_vector,
                                                      spacing = np.array([5,5,5]),
                                                      rotation = np.array([[0,-1,0],[1,0,0],[0,0,1]]),
                                                      origin = np.array([0,5,0]))
        if result_vector != expected_result_vector:
            successful_tested = 0
        self.simple_Task_Logging_Unit_Test_Outcome("Convert RAS to IJK", successful_tested)
    def unit_test_get_3x3x3_Matrix_From_Bigger_Matrix_at_one_Position(self):
        """Test get_3x3x3_Matrix_From_Bigger_Matrix_at_one_Position function"""
        successful_tested = 1
        # Example 1 - Border case
        input_x = 0
        input_y = 0
        input_z = 0
        input_array = np.arange(0,27,1).reshape((3,3,3))
        result = self.logic.get_3x3x3_Matrix_From_Bigger_Matrix_at_one_Position(input_x, input_y, input_z, input_array)
        expected_result = np.array([[[ 0, 0, 0],
                                     [ 0, 0, 0],
                                     [ 0, 0, 0]],
                                    [[ 0, 0, 0],
                                     [ 0, 0,  1],
                                     [ 0, 3,  4]],
                                    [[ 0, 0, 0],
                                     [ 0, 9, 10],
                                     [ 0, 12, 13]]])
        if np.linalg.norm(result-expected_result) > 0.001:
            successful_tested = 0
        # Example 2 - Outside case
        input_x = 6
        input_y = 6
        input_z = 6
        result = self.logic.get_3x3x3_Matrix_From_Bigger_Matrix_at_one_Position(input_x, input_y, input_z, input_array)
        expected_result = np.zeros((3,3,3))
        if np.linalg.norm(result-expected_result) > 0.001:
            successful_tested = 0
        # Example 3 - Null case
        input_x = 6
        input_y = 6
        input_z = 6
        input_array = None
        result = self.logic.get_3x3x3_Matrix_From_Bigger_Matrix_at_one_Position(input_x, input_y, input_z, input_array)
        expected_result = "get_3x3x3_Matrix_From_Bigger_Matrix_at_one_Position failed: Input matrix need to be a np.ndarray"
        if result != expected_result:
            successful_tested = 0
        self.simple_Task_Logging_Unit_Test_Outcome("Get 3x3x3 Matrix at one Position from a bigger Matrix ", successful_tested)
    def unit_test_get_2x2x2_Matrix_From_Bigger_Matrix_at_one_Position(self):
        """Test get_2x2x2_Matrix_From_Bigger_Matrix_at_one_Position function"""
        successful_tested = 1 
        # Example 1 - Border case
        input_x = 0.5
        input_y = 0.5
        input_z = 0.5
        input_array = np.arange(0,27,1).reshape((3,3,3))
        result = self.logic.get_2x2x2_Matrix_From_Bigger_Matrix_at_one_Position(input_x, input_y, input_z, input_array)
        expected_result = np.array([[[ 0, 1],
                                     [ 3, 4]],
                                    [[ 9, 10],
                                     [ 12, 13]]])
        if np.linalg.norm(result-expected_result) > 0.001:
            successful_tested = 0
        # Example 2 - Outside case
        input_x = 6
        input_y = 6
        input_z = 6
        result = self.logic.get_2x2x2_Matrix_From_Bigger_Matrix_at_one_Position(input_x, input_y, input_z, input_array)
        expected_result = np.zeros((2,2,2))
        if np.linalg.norm(result-expected_result) > 0.001:
            successful_tested = 0
        # Example 3 - Null case
        input_x = 6
        input_y = 6
        input_z = 6
        input_array = None
        result = self.logic.get_2x2x2_Matrix_From_Bigger_Matrix_at_one_Position(input_x, input_y, input_z, input_array)
        expected_result = "get_2x2x2_Matrix_From_Bigger_Matrix_at_one_Position failed: Input matrix need to be a np.ndarray"
        if result != expected_result:
            successful_tested = 0
        self.simple_Task_Logging_Unit_Test_Outcome("Get 2x2x2 Matrix at one Position from a bigger Matrix ", successful_tested)
    def unit_test_convert_Label_Volume_To_Model(self):
        """Test convert_Label_Volume_To_Model function"""
        successful_tested = 1
        # Example 1
        label_node = self.test_standard_label_volume
        expected_result_type = vtkMRMLModelNode
        result = self.logic.convert_Label_Volume_To_Model(label_node = label_node)
        if type(result) != expected_result_type:
            successful_tested = 0
        slicer.mrmlScene.RemoveNode(result)
        # Example 2
        label_node = self.test_standard_label_volume
        expected_result_type = vtkMRMLModelNode
        result = self.logic.convert_Label_Volume_To_Model(label_node = label_node)
        if type(result) != expected_result_type:
            successful_tested = 0
        slicer.mrmlScene.RemoveNode(result)
        self.simple_Task_Logging_Unit_Test_Outcome("Convert Label Volume to Model", successful_tested)

    def object_Creation_For_Testing_Creating_Box_All(self,
                                                     nodeNameEnd = "Standard",
                                                     imageSize = [32, 32, 32],
                                                     imageOrigin = [0.0, 0.0, 0.0],
                                                     imageSpacing = [1.0, 1.0, 1.0],
                                                     imageDirections = [[1,0,0], [0,1,0], [0,0,1]],
                                                     boxEdgeLength = [16,16,16]):
        """Create object for testing"""
        ###Create a volume
        nodeName = "Test_Volume_" + nodeNameEnd
        voxelType=vtk.VTK_UNSIGNED_CHAR
        fillVoxelValue = 0
        # Create an empty image volume, filled with fillVoxelValue
        imageData = vtk.vtkImageData()
        imageData.SetDimensions(imageSize)
        imageData.AllocateScalars(voxelType, 1)
        imageData.GetPointData().GetScalars().Fill(fillVoxelValue)
        # Edit the data to create a square
        for i in range(boxEdgeLength[0]):
            for j in range(boxEdgeLength[1]):
                for k in range(boxEdgeLength[2]):
                    imageData.SetScalarComponentFromFloat(i,j,k,0,1)
        # Create volume node
        volumeNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLScalarVolumeNode", nodeName)
        volumeNode.SetOrigin(imageOrigin)
        volumeNode.SetSpacing(imageSpacing)
        volumeNode.SetIJKToRASDirections(imageDirections)
        volumeNode.SetAndObserveImageData(imageData)
        volumeNode.CreateDefaultDisplayNodes()
        volumeNode.CreateDefaultStorageNode()
        # Move to desired folder
        self.shNode.SetItemParent(self.shNode.GetItemByDataNode(volumeNode), self.volumefortestfolderID)
        # Create a label map
        nodeName = "Test_Label_Volume_"+nodeNameEnd
        labelmapVolumeNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLLabelMapVolumeNode", nodeName)
        labelmapVolumeNode.SetOrigin(imageOrigin)
        labelmapVolumeNode.SetSpacing(imageSpacing)
        labelmapVolumeNode.SetIJKToRASDirections(imageDirections)
        labelmapVolumeNode.SetAndObserveImageData(imageData)
        labelmapVolumeNode.CreateDefaultDisplayNodes()
        labelmapVolumeNode.CreateDefaultStorageNode()
        # Move to desired folder
        self.shNode.SetItemParent(self.shNode.GetItemByDataNode(labelmapVolumeNode), self.labelvolumefortestfolderID)
        # Create a segmentation
        nodeName = "Test_Segmentation_"+nodeNameEnd
        segmentationNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLSegmentationNode", nodeName)
        slicer.modules.segmentations.logic().ImportLabelmapToSegmentationNode(labelmapVolumeNode, segmentationNode)
        # Move to desired folder
        self.shNode.SetItemParent(self.shNode.GetItemByDataNode(segmentationNode), self.segmentationfortestfolderID)
        # Create a model
        slicer.modules.segmentations.logic().ExportAllSegmentsToModels(segmentationNode, self.modelfortestfolderID)
        # Move to desired folder
        vtkIDlist = vtk.vtkIdList()
        self.shNode.GetItemChildren(self.modelfortestfolderID, vtkIDlist)
        self.shNode.SetItemName(vtkIDlist.GetId(vtkIDlist.GetNumberOfIds()-1), "Test_Model_"+nodeNameEnd)
        modelNode = self.shNode.GetItemDataNode(vtkIDlist.GetId(vtkIDlist.GetNumberOfIds()-1))
        # Move model folder to desired folder
        self.shNode.SetItemParent(self.modelfortestfolderID, self.shNode.GetSceneItemID())
        return volumeNode, labelmapVolumeNode, segmentationNode, modelNode
    def object_Creation_For_Testing_Creating_Box_Volume(self,
                                                nodeNameEnd = "Standard",
                                                imageSize = [32, 32, 32],
                                                imageOrigin = [0.0, 0.0, 0.0],
                                                imageSpacing = [1.0, 1.0, 1.0],
                                                imageDirections = [[1,0,0], [0,1,0], [0,0,1]]):
        ###Create a volume
        nodeName = "Test_Volume_" + nodeNameEnd
        voxelType=vtk.VTK_UNSIGNED_CHAR
        fillVoxelValue = 0
        # Create an empty image volume, filled with fillVoxelValue
        imageData = vtk.vtkImageData()
        imageData.SetDimensions(imageSize)
        imageData.AllocateScalars(voxelType, 1)
        imageData.GetPointData().GetScalars().Fill(fillVoxelValue)
        # Edit the data to create a square
        for i in range(16):
            for j in range(16):
                for k in range(16):
                    imageData.SetScalarComponentFromFloat(i,j,k,0,1)
        # Create volume node
        volumeNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLScalarVolumeNode", nodeName)
        volumeNode.SetOrigin(imageOrigin)
        volumeNode.SetSpacing(imageSpacing)
        volumeNode.SetIJKToRASDirections(imageDirections)
        volumeNode.SetAndObserveImageData(imageData)
        volumeNode.CreateDefaultDisplayNodes()
        volumeNode.CreateDefaultStorageNode()
        # Move to desired folder
        self.shNode.SetItemParent(self.shNode.GetItemByDataNode(volumeNode), self.volumefortestfolderID)
        return volumeNode
    def object_Creation_For_Testing_Creating_Box_Label_Volume(self,
                                                nodeNameEnd = "Standard",
                                                imageSize = [32, 32, 32],
                                                imageOrigin = [0.0, 0.0, 0.0],
                                                imageSpacing = [1.0, 1.0, 1.0],
                                                imageDirections = [[1,0,0], [0,1,0], [0,0,1]]):
        ###Create a label volume
        voxelType=vtk.VTK_UNSIGNED_CHAR
        fillVoxelValue = 0
        # Create an empty image volume, filled with fillVoxelValue
        imageData = vtk.vtkImageData()
        imageData.SetDimensions(imageSize)
        imageData.AllocateScalars(voxelType, 1)
        imageData.GetPointData().GetScalars().Fill(fillVoxelValue)
        # Edit the data to create a square
        for i in range(16):
            for j in range(16):
                for k in range(16):
                    imageData.SetScalarComponentFromFloat(i,j,k,0,1)
        # Create a label map
        nodeName = "Test_Label_Volume_"+nodeNameEnd
        labelmapVolumeNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLLabelMapVolumeNode", nodeName)
        labelmapVolumeNode.SetOrigin(imageOrigin)
        labelmapVolumeNode.SetSpacing(imageSpacing)
        labelmapVolumeNode.SetIJKToRASDirections(imageDirections)
        labelmapVolumeNode.SetAndObserveImageData(imageData)
        labelmapVolumeNode.CreateDefaultDisplayNodes()
        labelmapVolumeNode.CreateDefaultStorageNode()
        # Move to desired folder
        self.shNode.SetItemParent(self.shNode.GetItemByDataNode(labelmapVolumeNode), self.labelvolumefortestfolderID)
        return labelmapVolumeNode
    def object_Creation_For_Testing_Creating_Box_Segmentation(self,
                                                nodeNameEnd = "Standard",
                                                imageSize = [32, 32, 32],
                                                imageOrigin = [0.0, 0.0, 0.0],
                                                imageSpacing = [1.0, 1.0, 1.0],
                                                imageDirections = [[1,0,0], [0,1,0], [0,0,1]]):
        ###Create a label volume
        voxelType=vtk.VTK_UNSIGNED_CHAR
        fillVoxelValue = 0
        # Create an empty image volume, filled with fillVoxelValue
        imageData = vtk.vtkImageData()
        imageData.SetDimensions(imageSize)
        imageData.AllocateScalars(voxelType, 1)
        imageData.GetPointData().GetScalars().Fill(fillVoxelValue)
        # Edit the data to create a square
        for i in range(16):
            for j in range(16):
                for k in range(16):
                    imageData.SetScalarComponentFromFloat(i,j,k,0,1)
        # Create a label map
        nodeName = "Test_Label_Volume_"+nodeNameEnd
        labelmapVolumeNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLLabelMapVolumeNode", nodeName)
        labelmapVolumeNode.SetOrigin(imageOrigin)
        labelmapVolumeNode.SetSpacing(imageSpacing)
        labelmapVolumeNode.SetIJKToRASDirections(imageDirections)
        labelmapVolumeNode.SetAndObserveImageData(imageData)
        labelmapVolumeNode.CreateDefaultDisplayNodes()
        labelmapVolumeNode.CreateDefaultStorageNode()
        # Create a segmentation
        nodeName = "Test_Segmentation_"+nodeNameEnd
        segmentationNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLSegmentationNode", nodeName)
        slicer.modules.segmentations.logic().ImportLabelmapToSegmentationNode(labelmapVolumeNode, segmentationNode)
        # Move to desired folder
        self.shNode.SetItemParent(self.shNode.GetItemByDataNode(segmentationNode), self.segmentationfortestfolderID)
        slicer.mrmlScene.RemoveNode(labelmapVolumeNode)
        return segmentationNode
    def object_Creation_For_Testing_Creating_Box_Model(self,
                                                nodeNameEnd = "Standard",
                                                imageSize = [32, 32, 32],
                                                imageOrigin = [0.0, 0.0, 0.0],
                                                imageSpacing = [1.0, 1.0, 1.0],
                                                imageDirections = [[1,0,0], [0,1,0], [0,0,1]]):
        ###Create a label volume
        voxelType=vtk.VTK_UNSIGNED_CHAR
        fillVoxelValue = 0
        # Create an empty image volume, filled with fillVoxelValue
        imageData = vtk.vtkImageData()
        imageData.SetDimensions(imageSize)
        imageData.AllocateScalars(voxelType, 1)
        imageData.GetPointData().GetScalars().Fill(fillVoxelValue)
        # Edit the data to create a square
        for i in range(16):
            for j in range(16):
                for k in range(16):
                    imageData.SetScalarComponentFromFloat(i,j,k,0,1)
        # Create a label map
        nodeName = "Test_Label_Volume_"+nodeNameEnd
        labelmapVolumeNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLLabelMapVolumeNode", nodeName)
        labelmapVolumeNode.SetOrigin(imageOrigin)
        labelmapVolumeNode.SetSpacing(imageSpacing)
        labelmapVolumeNode.SetIJKToRASDirections(imageDirections)
        labelmapVolumeNode.SetAndObserveImageData(imageData)
        labelmapVolumeNode.CreateDefaultDisplayNodes()
        labelmapVolumeNode.CreateDefaultStorageNode()
        # Create a segmentation and model
        nodeName = "Test_Segmentation_"+nodeNameEnd
        segmentationNode = slicer.mrmlScene.AddNewNodeByClass("vtkMRMLSegmentationNode", nodeName)
        slicer.modules.segmentations.logic().ImportLabelmapToSegmentationNode(labelmapVolumeNode, segmentationNode)
        slicer.modules.segmentations.logic().ExportAllSegmentsToModels(segmentationNode, self.modelfortestfolderID)
        # self.shNode.SetItemParent(exportModelFolderItemId, self.shNode.GetSceneItemID())
        vtkIDlist = vtk.vtkIdList()
        self.shNode.GetItemChildren(self.modelfortestfolderID, vtkIDlist)
        self.shNode.SetItemName(vtkIDlist.GetId(vtkIDlist.GetNumberOfIds()-1), "Test_Model_"+nodeNameEnd)
        modelNode = self.shNode.GetItemDataNode(vtkIDlist.GetId(vtkIDlist.GetNumberOfIds()-1))
        # Move model folder to desired folder
        self.shNode.SetItemParent(self.modelfortestfolderID, self.shNode.GetSceneItemID())
        slicer.mrmlScene.RemoveNode(labelmapVolumeNode)
        slicer.mrmlScene.RemoveNode(segmentationNode)
        return modelNode

    def simple_Task_Create_Folder(self, folder_name):
        """Create a folder and collapse it"""
        folder_ID = self.shNode.CreateFolderItem(self.shNode.GetSceneItemID(), folder_name)
        # Hide the folder
        pluginHandler = slicer.qSlicerSubjectHierarchyPluginHandler().instance()
        volPlugin = pluginHandler.getOwnerPluginForSubjectHierarchyItem(folder_ID)
        volPlugin.setDisplayVisibility(folder_ID, 0)
        # Collapse the folder
        self.shNode.SetItemExpanded(folder_ID, 0)
        return folder_ID
    def simple_Task_Logging_Test_Outcome(self, test_name = "Standard", successful_tested = False):
        """Logging test results"""
        if successful_tested:
            self.logger_custom.info("Test passed: " + test_name)
            self.delayDisplay("Test passed: " + test_name)
        else:
            self.logger_custom.warning("Test failed: " + test_name)         
    def simple_Task_Logging_Unit_Test_Outcome(self, test_name = "Standard", successful_tested = False):
        """Logging unit test results"""
        if successful_tested:
            self.logger_custom.info("Unit test passed: " + test_name)
        else:
            self.logger_custom.warning("Unit test failed: " + test_name)



