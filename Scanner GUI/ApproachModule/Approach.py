import sys
from PyQt4 import QtGui, QtCore, uic
from twisted.internet.defer import inlineCallbacks, Deferred
import numpy as np
import time

path = sys.path[0] + r"\ApproachModule"
ScanControlWindowUI, QtBaseClass = uic.loadUiType(path + r"\Approach.ui")
Ui_ServerList, QtBaseClass = uic.loadUiType(path + r"\requiredServers.ui")
Ui_advancedApproachSettings, QtBaseClass = uic.loadUiType(path + r"\advancedApproachSettings.ui")
Ui_advancedFeedbackSettings, QtBaseClass = uic.loadUiType(path + r"\advancedFeedbackSettings.ui")
Ui_MeasurementSettings, QtBaseClass = uic.loadUiType(path + r"\MeasurementSettings.ui")

class Window(QtGui.QMainWindow, ScanControlWindowUI):
    def __init__(self, reactor, parent=None):
        super(Window, self).__init__(parent)
        self.feedback = False
        
        self.reactor = reactor
        self.setupUi(self)
        self.setupAdditionalUi()

        self.moveDefault()        


        #Connect show servers list pop up
        self.push_Servers.clicked.connect(self.showServersList)
        
        #Connect measurement buttons
        self.push_StartControllers.clicked.connect(self.toggleControllers)
        self.push_toggleFeedback.clicked.connect(self.toggleFeedback)
        
        #Connect advanced setting pop up menues
        self.push_AdvancedApproach.clicked.connect(self.showAdvancedApproach)
        self.push_AdvancedFeedback.clicked.connect(self.showAdvancedFeedback)
        self.push_MeasurementSettings.clicked.connect(self.showMeasurementSettings)
        
        #Connect incrementing buttons
        self.push_addFreq.clicked.connect(self.incrementFreqThresh)
        self.push_addField.clicked.connect(self.incrementFieldThresh)
        self.push_addTemp.clicked.connect(self.incrementTempThresh)
        self.push_subFreq.clicked.connect(self.decrementFreqThresh)
        self.push_subField.clicked.connect(self.decrementFieldThresh)
        self.push_subTemp.clicked.connect(self.decrementTempThresh)
        
        self.lineEdit_freqSet.editingFinished.connect(self.setFreqThresh)
        self.lineEdit_tempSet.editingFinished.connect(self.setTempThresh)
        self.lineEdit_fieldSet.editingFinished.connect(self.setFieldThresh)
        
        self.push_Approach.clicked.connect(self.startApproachSequence)
        self.push_Approach_Abort.clicked.connect(self.abortApproachSequence)
        
        self.push_Withdraw.clicked.connect(self.withdrawSpecifiedDistance)
        self.lineEdit_Withdraw.editingFinished.connect(self.setWithdrawDistance)
        #Initialize all the labrad connections as none
        self.cxn = None
        self.dv = None
        self.hf = None
        
        #Initialize values
        self.freqThreshold = 1.00
        self.tempThreshold = 1e-4
        self.fieldThreshold = 1e-4
        
        self.measuring = False
        self.approaching = False
        
        self.setFreqThresh()
        self.setTempThresh()
        self.setFieldThresh()
        
        self.PLL_TargetBW = 100
        # 0 is just proportional term, 1 is just integral term, 2 is proportional
        # and intergral, and 3 is proportional, integral, and derivative term
        self.PLL_AdviseMode = 2
        
        self.PLL_Input  = 2
        self.PLL_CenterFreq = None
        self.PLL_CenterPhase = None
        self.PLL_Range = 20
        
        self.PLL_Harmonic = 1
        self.PLL_TC = 138.4e-6
        self.PLL_FilterBW = 500.1
        self.PLL_FilterOrder = 4
        
        self.PLL_P = 2.537
        self.PLL_I = 3.282
        self.PLL_D = 0 
        self.PLL_SimBW = 272.2
        self.PLL_PM = 61.72
        self.PLL_Rate = 1.842e+6

        self.PLL_Output = 1
        self.PLL_Output_Amp = 0.01
        
        self.FT_Input = 1
        self.FT_Frequency = 20000
        self.FT_Output = 3
        self.FT_Amplitude = 0.1
        
        self.F_Demod = 1
        self.F_Harmonic = 1
        self.F_TC = 0.001
        
        self.T_Demod = 1
        self.T_Harmonic = 2
        self.T_TC = 0.001
        
        
        self.Atto_Z_DAC_Out = 1 #Output channel from dac that goes to Z of attocubes
        self.Atto_Z_DAC_Voltage = 0
        self.Approach_MeasTime = 1 #In seconds
        
        self.Atto_Z_Step = 5e-9 #in units of meters
        self.Atto_Z_Points = 50
        self.Atto_Z_Delay = 1e-3 #in units of seconds
        self.Atto_Z_Speed = 5e-9 / (50 * 1e-3) #in units of meters per seconds
        
        #Attocube always retracts the whole range (24 um) before 
        self.Atto_Retract_Points = 1000
        self.Atto_Retract_Delay = 5e-4
        self.Atto_Retract_Speed = 24e-6 / (50*5e-4)
        
        self.JPE_Tip_Height = 24e-3 #in meters
        self.JPE_Module_Address = 1
        
        self.JPE_Approach_Steps = 1000
        self.JPE_Approach_Size = 100
        self.JPE_Approach_Freq = 600 
        
        self.JPE_Retract_Steps = 10000
        self.JPE_Retract_Size = 100
        self.JPE_Retract_Freq = 600 
        
        self.Temperature = 293 #in kelvin
        self.z_volts_to_meters = 10/ 24e-6 #24 microns corresponds to 10 volts, eventually value should depend on temperature
        
        self.withdrawDistance = 2e-6
        
        self.lockInterface()
        
    def moveDefault(self):    
        self.move(10,170)
        
    def connectLabRAD(self, dict):
        try:
            self.unlockInterface()
            self.cxn = dict['cxn']
            self.hf = dict['hf2li']
            self.dac = dict['dac_adc']
            self.cpsc = dict['cpsc']
            self.push_Servers.setStyleSheet("#push_Servers{" + 
            "background: rgb(0, 170, 0);border-radius: 4px;}")
        except:
            self.push_Servers.setStyleSheet("#push_Servers{" + 
            "background: rgb(161, 0, 0);border-radius: 4px;}")  
        if self.cxn is None or self.hf is None or self.dac is None or self.cpsc is None:
            self.push_Servers.setStyleSheet("#push_Servers{" + 
            "background: rgb(161, 0, 0);border-radius: 4px;}")
            self.unlockInterface()
            
    def disconnectLabRAD(self):
        self.dv = None
        self.cxn = None
        self.push_Servers.setStyleSheet("#push_Servers{" + 
            "background: rgb(144, 140, 9);border-radius: 4px;}")
            
    def showServersList(self):
        serList = serversList(self.reactor, self)
        serList.exec_()
        
    def showAdvancedApproach(self):
        atto_z_values = [self.Approach_MeasTime,self.Atto_Z_Step, self.Atto_Z_Points,self.Atto_Z_Delay, 
                        self.Atto_Z_Speed, self.Atto_Retract_Points,  self.Atto_Retract_Delay, self.Atto_Retract_Speed, 
                        self.Atto_Z_DAC_Out]
                      
        JPE_values = [self.JPE_Tip_Height, self.JPE_Module_Address, self.JPE_Approach_Steps, self.JPE_Approach_Size, 
                        self.JPE_Approach_Freq, self.JPE_Retract_Steps, self.JPE_Retract_Size, self.JPE_Retract_Freq, self.Temperature]
                        
        advApp = advancedApproachSettings(self.reactor, atto_z_values, JPE_values, self)
        
        if advApp.exec_():
            atto_z_values, JPE_values = advApp.getValues()
            
            self.Approach_MeasTime = atto_z_values[0]
        
            self.Atto_Z_Step = atto_z_values[1]
            self.Atto_Z_Points = atto_z_values[2]
            self.Atto_Z_Delay = atto_z_values[3]
            self.Atto_Z_Speed = atto_z_values[4]
            
            self.Atto_Retract_Points = atto_z_values[5]
            self.Atto_Retract_Delay = atto_z_values[6]
            self.Atto_Retract_Speed = atto_z_values[7]
            
            self.Atto_Z_DAC_Out = atto_z_values[8]
            
            self.JPE_Tip_Height = JPE_values[0]
            self.JPE_Module_Address = JPE_values[1]
            
            self.JPE_Approach_Steps = JPE_values[2]
            self.JPE_Approach_Size = JPE_values[3]
            self.JPE_Approach_Freq = JPE_values[4]
            
            self.JPE_Retract_Steps = JPE_values[5]
            self.JPE_Retract_Size = JPE_values[6]
            self.JPE_Retract_Freq = JPE_values[7]
        
            self.Temperature = JPE_values[8]
        
    def showAdvancedFeedback(self):
        advFeed = advancedFeedbackSettings(self.reactor, 0, self)
        advFeed.exec_()
        
    def showMeasurementSettings(self):
        PLL_Values = [self.PLL_TargetBW, self.PLL_AdviseMode, self.PLL_Input, self.PLL_CenterFreq, self.PLL_CenterPhase, 
                        self.PLL_Range, self.PLL_Harmonic, self.PLL_TC, self.PLL_FilterBW, self.PLL_FilterOrder, 
                        self.PLL_P, self.PLL_I, self.PLL_D, self.PLL_SimBW, self.PLL_PM, self.PLL_Rate, self.PLL_Output,
                        self.PLL_Output_Amp]        
        FT_Values = [self.FT_Input, self.FT_Frequency, self.FT_Output, self.FT_Amplitude, self.F_Demod, 
                        self.F_Harmonic, self.F_TC, self.T_Demod, self.T_Harmonic, self.T_TC]
        MeasSet = MeasurementSettings(self.reactor, PLL_Values, FT_Values, parent = self, server = self.hf)
        if MeasSet.exec_():
            PLL_Values, FT_Values = MeasSet.getValues()
            
            self.PLL_TargetBW = PLL_Values[0]
            self.PLL_AdviseMode = PLL_Values[1]
        
            self.PLL_Input  = PLL_Values[2]
            self.PLL_CenterFreq = PLL_Values[3]
            self.PLL_CenterPhase = PLL_Values[4]
            self.PLL_Range = PLL_Values[5]
            
            self.PLL_Harmonic = PLL_Values[6]
            self.PLL_TC = PLL_Values[7]
            self.PLL_FilterBW = PLL_Values[8]
            self.PLL_FilterOrder = PLL_Values[9]
            
            self.PLL_P = PLL_Values[10]
            self.PLL_I = PLL_Values[11]
            self.PLL_D = PLL_Values[12] 
            self.PLL_SimBW = PLL_Values[13]
            self.PLL_PM = PLL_Values[14]
            self.PLL_Rate = PLL_Values[15]

            self.PLL_Output = PLL_Values[16]
            self.PLL_Output_Amp = PLL_Values[17]
            
            self.FT_Input = FT_Values[0]
            self.FT_Frequency = FT_Values[1]
            self.FT_Output = FT_Values[2]
            self.FT_Amplitude = FT_Values[3]
            
            self.F_Demod = FT_Values[4]
            self.F_Harmonic = FT_Values[5]
            self.F_TC = FT_Values[6]
            
            self.T_Demod = FT_Values[7]
            self.T_Harmonic = FT_Values[8]
            self.T_TC = FT_Values[9]
        
    def setupAdditionalUi(self):
        self.fieldSlider.close()
        self.fieldSlider = MySlider(parent = self.centralwidget)
        self.fieldSlider.setGeometry(120,85,260,70)
        self.fieldSlider.setMinimum(0)
        self.fieldSlider.setMaximum(1000000)
        self.fieldSlider.setStyleSheet("QSlider::groove:horizontal {border: 1px solid #bbb;background: white;height: 10px;border-radius: 4px;}QSlider::sub-page:horizontal {background: qlineargradient(x1: 0, y1: 0,    x2: 0, y2: 1,    stop: 0 #66e, stop: 1 #bbf);background: qlineargradient(x1: 0, y1: 0.2, x2: 1, y2: 1,    stop: 0 #bbf, stop: 1 #55f);border: 1px solid #777;height: 10px;border-radius: 4px;}QSlider::add-page:horizontal {background: #fff;border: 1px solid #777;height: 10px;border-radius: 4px;}QSlider::handle:horizontal {background: qlineargradient(x1:0, y1:0, x2:1, y2:1,    stop:0 #eee, stop:1 #ccc);border: 1px solid #777;width: 13px;margin-top: -2px;margin-bottom: -2px;border-radius: 4px;}QSlider::handle:horizontal:hover {background: qlineargradient(x1:0, y1:0, x2:1, y2:1,    stop:0 #fff, stop:1 #ddd);border: 1px solid #444;border-radius: 4px;}QSlider::sub-page:horizontal:disabled {background: #bbb;border-color: #999;}QSlider::add-page:horizontal:disabled {background: #eee;border-color: #999;}QSlider::handle:horizontal:disabled {background: #eee;border: 1px solid #aaa;border-radius: 4px;}")
        self.fieldSlider.setTickPos([8e-6, 1e-5, 2e-5, 4e-5, 6e-5, 8e-5, 1e-4, 2e-4, 4e-4, 6e-4, 8e-4,1e-3, 2e-3])
        self.fieldSlider.setNumPos([1e-5,1e-4,1e-3])
        self.fieldSlider.lower()
        
        self.tempSlider.close()
        self.tempSlider = MySlider(parent = self.centralwidget)
        self.tempSlider.setGeometry(120,175,260,70)
        self.tempSlider.setMinimum(0)
        self.tempSlider.setMaximum(1000000)
        self.tempSlider.setStyleSheet("QSlider::groove:horizontal {border: 1px solid #bbb;background: white;height: 10px;border-radius: 4px;}QSlider::sub-page:horizontal {background: qlineargradient(x1: 0, y1: 0,    x2: 0, y2: 1,    stop: 0 #66e, stop: 1 #bbf);background: qlineargradient(x1: 0, y1: 0.2, x2: 1, y2: 1,    stop: 0 #bbf, stop: 1 #55f);border: 1px solid #777;height: 10px;border-radius: 4px;}QSlider::add-page:horizontal {background: #fff;border: 1px solid #777;height: 10px;border-radius: 4px;}QSlider::handle:horizontal {background: qlineargradient(x1:0, y1:0, x2:1, y2:1,    stop:0 #eee, stop:1 #ccc);border: 1px solid #777;width: 13px;margin-top: -2px;margin-bottom: -2px;border-radius: 4px;}QSlider::handle:horizontal:hover {background: qlineargradient(x1:0, y1:0, x2:1, y2:1,    stop:0 #fff, stop:1 #ddd);border: 1px solid #444;border-radius: 4px;}QSlider::sub-page:horizontal:disabled {background: #bbb;border-color: #999;}QSlider::add-page:horizontal:disabled {background: #eee;border-color: #999;}QSlider::handle:horizontal:disabled {background: #eee;border: 1px solid #aaa;border-radius: 4px;}")
        self.tempSlider.setTickPos([8e-6, 1e-5, 2e-5, 4e-5, 6e-5, 8e-5, 1e-4, 2e-4, 4e-4, 6e-4, 8e-4,1e-3, 2e-3])
        self.tempSlider.setNumPos([1e-5,1e-4,1e-3])
        self.tempSlider.lower()
        
        self.freqSlider.close()
        self.freqSlider = MySlider(parent = self.centralwidget)
        self.freqSlider.setGeometry(120,265,260,70)
        self.freqSlider.setMinimum(0)
        self.freqSlider.setMaximum(1000000)
        self.freqSlider.setStyleSheet("QSlider::groove:horizontal {border: 1px solid #bbb;background: white;height: 10px;border-radius: 4px;}QSlider::sub-page:horizontal {background: qlineargradient(x1: 0, y1: 0,    x2: 0, y2: 1,    stop: 0 #66e, stop: 1 #bbf);background: qlineargradient(x1: 0, y1: 0.2, x2: 1, y2: 1,    stop: 0 #bbf, stop: 1 #55f);border: 1px solid #777;height: 10px;border-radius: 4px;}QSlider::add-page:horizontal {background: #fff;border: 1px solid #777;height: 10px;border-radius: 4px;}QSlider::handle:horizontal {background: qlineargradient(x1:0, y1:0, x2:1, y2:1,    stop:0 #eee, stop:1 #ccc);border: 1px solid #777;width: 13px;margin-top: -2px;margin-bottom: -2px;border-radius: 4px;}QSlider::handle:horizontal:hover {background: qlineargradient(x1:0, y1:0, x2:1, y2:1,    stop:0 #fff, stop:1 #ddd);border: 1px solid #444;border-radius: 4px;}QSlider::sub-page:horizontal:disabled {background: #bbb;border-color: #999;}QSlider::add-page:horizontal:disabled {background: #eee;border-color: #999;}QSlider::handle:horizontal:disabled {background: #eee;border: 1px solid #aaa;border-radius: 4px;}")
        self.freqSlider.setTickPos([0.08, 0.1,0.2,0.4,0.6, 0.8,1, 2, 4, 6, 8, 10, 20])
        self.freqSlider.setNumPos([0.1,1,10])
        self.freqSlider.lower()
        
        self.freqSlider.logValueChanged.connect(self.updateFreqThresh)
        self.fieldSlider.logValueChanged.connect(self.updateFieldThresh)
        self.tempSlider.logValueChanged.connect(self.updateTempThresh)
        
#--------------------------------------------------------------------------------------------------------------------------#
            
    """ The following section connects actions related to updating thresholds."""
        
    def updateFreqThresh(self, val):
        self.lineEdit_freqSet.setText(formatNum(val))
        self.freqThreshold = val
        
    def setFreqThresh(self):
        new_freqThresh = str(self.lineEdit_freqSet.text())
        val = readNum(new_freqThresh)
        if isinstance(val,float):
            if val < 0.08:
                val = 0.08
            elif val > 20:
                val = 20
        self.freqThreshold = val
        self.lineEdit_freqSet.setText(formatNum(self.freqThreshold))
        self.freqSlider.setPosition(self.freqThreshold)
    
    def incrementFreqThresh(self):
        val = self.freqThreshold * 1.005
        if val < 0.08:
            val = 0.8
        elif val > 20:
            val = 20
        self.lineEdit_freqSet.setText(formatNum(self.freqThreshold))
        self.setFreqThresh()
        self.updateFreqThresh(val)
        
    def decrementFreqThresh(self):
        val = self.freqThreshold * 0.995
        if val < 0.08:
            val = 0.08
        elif val > 20:
            val = 20
        self.lineEdit_freqSet.setText(formatNum(self.freqThreshold))
        self.setFreqThresh()
        self.updateFreqThresh(val)
        
    def updateFieldThresh(self,val):
        self.lineEdit_fieldSet.setText(formatNum(val))
        self.fieldThreshold = val
        
    def setFieldThresh(self):
        new_fieldThresh = str(self.lineEdit_fieldSet.text())
        val = readNum(new_fieldThresh)
        if isinstance(val,float):
            if val < 8e-6:
                val = 8e-6
            elif val > 2e-3:
                val = 2e-3
            self.fieldThreshold = val
        self.lineEdit_fieldSet.setText(formatNum(self.fieldThreshold))
        self.fieldSlider.setPosition(self.fieldThreshold)
        
    def incrementFieldThresh(self):
        val = self.fieldThreshold * 1.005
        if val < 8e-6:
            val = 8e-6
        elif val > 2e-3:
            val = 2e-3
        self.lineEdit_fieldSet.setText(formatNum(self.fieldThreshold))
        self.setFieldThresh()
        self.updateFieldThresh(val)
        
    def decrementFieldThresh(self):
        val = self.fieldThreshold * 0.995
        if val < 8e-6:
            val = 8e-6
        elif val > 2e-3:
            val = 2e-3
        self.lineEdit_fieldSet.setText(formatNum(self.fieldThreshold))
        self.setFieldThresh()
        self.updateFieldThresh(val)
        
    def updateTempThresh(self,val):
        self.lineEdit_tempSet.setText(formatNum(val))
        self.tempThreshold = val
        
    def setTempThresh(self):
        new_tempThresh = str(self.lineEdit_tempSet.text())
        val = readNum(new_tempThresh)
        if isinstance(val,float):
            if val < 8e-6:
                val = 8e-6
            elif val > 2e-3:
                val = 2e-3
            self.tempThreshold = val
        self.lineEdit_tempSet.setText(formatNum(self.tempThreshold))
        self.tempSlider.setPosition(self.tempThreshold)
        
    def incrementTempThresh(self):
        val = self.tempThreshold * 1.005
        if val < 8e-6:
            val = 8e-6
        elif val > 2e-3:
            val = 2e-3
        self.lineEdit_tempSet.setText(formatNum(self.tempThreshold))
        self.setTempThresh()
        self.updateTempThresh(val)
        
    def decrementTempThresh(self):
        val = self.tempThreshold * 0.995
        if val < 8e-6:
            val = 8e-6
        elif val > 2e-3:
            val = 2e-3
        self.lineEdit_tempSet.setText(formatNum(self.tempThreshold))
        self.setTempThresh()
        self.updateTempThresh(val)
        
#--------------------------------------------------------------------------------------------------------------------------#
            
    """ The following section connects actions related to toggling measurements."""
    @inlineCallbacks
    def toggleControllers(self, c = None):
        if not self.measuring:
            self.push_StartControllers.setText("Stop Controllers")  
            style = """ QPushButton#push_StartControllers{
                    color: rgb(50,168,50);
                    background-color:rgb(0,0,0);
                    border: 1px solid rgb(50,168,50);
                    border-radius: 5px
                    }  
                    QPushButton:pressed#push_StartControllers{
                    color: rgb(168,168,168);
                    background-color:rgb(95,107,166);
                    border: 1px solid rgb(168,168,168);
                    border-radius: 5px
                    }
                    """
            self.push_StartControllers.setStyleSheet(style)
            self.measuring = True
            self.push_MeasurementSettings.setEnabled(False)
            
            if self.checkBox_Field.isChecked():
                print 'Starting field measurement'
            if self.checkBox_Freq.isChecked():
                yield self.setHF2LI_PLL_Settings()
                yield self.startFrequencyMonitoring()
            if self.checkBox_Temp.isChecked():
                print 'Starting temp measurement'
        else: 
            self.push_StartControllers.setText("Start Controllers")
            style = """ QPushButton#push_StartControllers{
                    color: rgb(168,168,168);
                    background-color:rgb(0,0,0);
                    border: 1px solid rgb(168,168,168);
                    border-radius: 5px
                    }  
                    QPushButton:pressed#push_StartControllers{
                    color: rgb(168,168,168);
                    background-color:rgb(95,107,166);
                    border: 1px solid rgb(168,168,168);
                    border-radius: 5px
                    }
                    """
            self.push_StartControllers.setStyleSheet(style)
            self.measuring = False
            self.push_MeasurementSettings.setEnabled(True)
            
    def setWorkingPoint(self, freq, phase, out, amp):
        self.checkBox_Freq.setCheckable(True)
        self.push_CenterSet.setStyleSheet("""#push_CenterSet{
                                            background: rgb(0, 170, 0);
                                            border-radius: 5px;
                                            }""")
        self.PLL_CenterFreq = freq
        self.PLL_CenterPhase = phase
        self.PLL_Output = out
        self.PLL_Output_Amp = amp
        
    @inlineCallbacks
    def setHF2LI_PLL_Settings(self, c = None):
        try:
            #All settings are set for PLL 1
            yield self.hf.set_pll_input(1,self.PLL_Input)
            yield self.hf.set_pll_freqcenter(1, self.PLL_CenterFreq)
            yield self.hf.set_pll_setpoint(1,self.PLL_CenterPhase)
            yield self.hf.set_pll_freqrange(1,self.PLL_Range)
            
            yield self.hf.set_pll_harmonic(1,self.PLL_Harmonic)
            yield self.hf.set_pll_tc(1,self.PLL_TC)
            self.PLL_TC = yield self.hf.get_pll_tc(1)
            self.PLL_FilterBW = 0.0692291283 / self.PLL_TC
            
            yield self.hf.set_pll_filterorder(1,self.PLL_FilterOrder)
            
            yield self.hf.set_pll_p(1,self.PLL_P)
            yield self.hf.set_pll_i(1,self.PLL_I)
            yield self.hf.set_pll_d(1,self.PLL_D)
            #These don't work yet, but should be added once they do
            #yield self.hf.set_PLL_rate(1,self.PLL_Rate)
            #self.PLL_Rate = yield self.hf.get_PLL_rate(1)
        except Exception as inst:
            print inst
        
    @inlineCallbacks
    def startFrequencyMonitoring(self, c=None):
        try:
            #All settings are set for PLL 1
            yield self.hf.set_pll_on(1)
            while self.measuring:
                deltaf = None
                phaseError = None
                data = yield self.hf.poll_pll(1, 0.15, 100)
                try:
                    deltaf = data[0][0]
                except:
                    pass
                try:
                    phaseError = data[1][0]
                except:
                    pass
                if deltaf is not None:
                    self.lineEdit_freqCurr.setText(formatNum(deltaf))
                if phaseError is not None:
                    self.lineEdit_phaseError.setText(formatNum(phaseError))

            yield self.hf.set_pll_off(1)
        except Exception as inst:
            print inst
        
    def toggleFeedback(self):
        if self.feedback:
            self.push_toggleFeedback.setText('Off')
            self.push_toggleFeedback.setStyleSheet("#push_toggleFeedback{color: rgb(168,50,50);background-color:rgb(0,0,0);border: 2px solid rgb(168,50,50);border-radius: 5px}")
            self.feedback = False
        else:
            self.push_toggleFeedback.setText('On')
            self.push_toggleFeedback.setStyleSheet("#push_toggleFeedback{color: rgb(50,168,50);background-color:rgb(0,0,0);border: 2px solid rgb(50,168,50);border-radius: 5px}")
            self.feedback = True
            
#--------------------------------------------------------------------------------------------------------------------------#
    """ The following section contains the approach sequence."""
    
    @inlineCallbacks
    def startApproachSequence(self, c = None):
        self.approaching = True
        
        #yield self.cpsc.set_height(self.JPE_Tip_Height*1000 + 33.9)
        
        while self.approaching:
            yield self.sleep(0.25)
            
            #data = yield self.hf.poll_pll(1, self.Approach_MeasTime, 500)
            #df_avg = np.avg(data[0])
            #if dv_avg > self.freqThreshold:
            #    self.approaching = False
            #    break
            #Here need to compute conversion rate between voltage and step size
            start_voltage = self.Atto_Z_DAC_Voltage
            end_voltage = self.Atto_Z_DAC_Voltage + self.Atto_Z_Step * self.z_volts_to_meters
            if end_voltage < 10 and self.approaching:
                #yield self.dac.buffer_ramp([self.Atto_Z_DAC_Out],[],[start_voltage],[end_voltage], self.Atto_Z_Points, self.Atto_Z_Delay * 1e6)
                self.lineEdit_FineZ.setText(formatNum(end_voltage / self.z_volts_to_meters))
                self.Atto_Z_DAC_Voltage = end_voltage
                self.progressBar.setValue(int(100*self.Atto_Z_DAC_Voltage))
            elif self.approaching:
                end_voltage = 0
                self.Atto_Z_DAC_Voltage = end_voltage
                self.progressBar.setValue(int(100*self.Atto_Z_DAC_Voltage))
                #retract atto
                #yield self.dac.buffer_ramp([self.Atto_Z_DAC_Out],[],[start_voltage],[end_voltage], self.Atto_Retract_Points, self.Atto_Retract_Delay * 1e6)
                self.lineEdit_FineZ.setText(formatNum(end_voltage / self.z_volts_to_meters))
                #Do a coarse step forward
                #yield self.cpsc.move_z(self.JPE_Module_Address, self.Temperature, , self.JPE_Approach_Freq, self.JPE_Approach_Size, self.JPE_Approach_Steps)
            print 'Starting at voltage: ' + str(start_voltage) + '. Finishing at voltage: ' + str(end_voltage)
            
            #measure deltaf, get average value
            #if below threshold, step by specified step size
            #repeat until full z voltage
            #retract entire way 
            #step forward with JPEs
            #repeat atto cube process
                
    
    def abortApproachSequence(self):
        self.approaching = False
        
    @inlineCallbacks
    def withdrawSpecifiedDistance(self, c = None):
        try:
            #Eventually add a way to make sure that the DAC / JPEs are no longer moving anything before sending the retract command
            self.approaching = False
            start_voltage = self.Atto_Z_DAC_Voltage
            end_voltage = self.Atto_Z_DAC_Voltage - self.withdrawDistance * self.z_volts_to_meters
            
            if end_voltage < 0:
                end_voltage = 0
                #eventually send message saying can't withdraw distance without coarse movement
                
            yield self.sleep(0.25)
            
            retract_delay =  int(1e6*self.withdrawDistance / (self.Atto_Retract_Speed * self.Atto_Retract_Points))
            if retract_delay < 100:
                retract_delay = 100
            print 'Retract delay in microseconds: ' + str(retract_delay)
            #yield self.dac.ramp1(self.Atto_Z_DAC_Out, start_voltage, end_voltage, self.Atto_Retract_Points,retract_delay)
            
            self.Atto_Z_DAC_Voltage = end_voltage
            self.progressBar.setValue(int(100*self.Atto_Z_DAC_Voltage))
            self.lineEdit_FineZ.setText(formatNum(self.Atto_Z_DAC_Voltage / self.z_volts_to_meters))
        except Exception as inst:
            print inst
        
        
    def setWithdrawDistance(self):
        val = readNum(str(self.lineEdit_Withdraw.text()))
        if isinstance(val,float):
            if val < 0:
                val = 0
            elif val > 24e-6:
                val = 24e-6
            self.withdrawDistance = val
        self.lineEdit_Withdraw.setText(formatNum(self.withdrawDistance))

#----------------------------------------------------------------------------------------------#         
    """ The following section has generally useful functions."""  
    
    def lockInterface(self):
        self.push_Home.setEnabled(False)
        self.push_Withdraw.setEnabled(False)
        self.push_StartControllers.setEnabled(False)
        self.push_MeasurementSettings.setEnabled(False)
        self.push_Approach.setEnabled(False)
        self.push_toggleFeedback.setEnabled(False)
        self.push_AdvancedApproach.setEnabled(False)
        self.push_AdvancedFeedback.setEnabled(False)
        
        self.lineEdit_Withdraw.setDisabled(True)
        self.lineEdit_fieldSet.setDisabled(True)
        self.lineEdit_tempSet.setDisabled(True)
        self.lineEdit_freqSet.setDisabled(True)
        self.lineEdit_FineZ.setDisabled(True)
        
        self.comboBox_FeedbackOutput.setEnabled(False)
        
        self.fieldSlider.setEnabled(False)
        self.tempSlider.setEnabled(False)
        self.freqSlider.setEnabled(False)
        
    def unlockInterface(self):
        self.push_Home.setEnabled(True)
        self.push_Withdraw.setEnabled(True)
        self.push_StartControllers.setEnabled(True)
        self.push_MeasurementSettings.setEnabled(True)
        self.push_Approach.setEnabled(True)
        self.push_toggleFeedback.setEnabled(True)
        self.push_AdvancedApproach.setEnabled(True)
        self.push_AdvancedFeedback.setEnabled(True)
        
        self.lineEdit_Withdraw.setDisabled(False)
        self.lineEdit_fieldSet.setDisabled(False)
        self.lineEdit_tempSet.setDisabled(False)
        self.lineEdit_freqSet.setDisabled(False)
        self.lineEdit_FineZ.setDisabled(False)
    
        self.comboBox_FeedbackOutput.setEnabled(True)
        
        self.fieldSlider.setEnabled(True)
        self.tempSlider.setEnabled(True)
        self.freqSlider.setEnabled(True)
        
    def sleep(self,secs):
        """Asynchronous compatible sleep command. Sleeps for given time in seconds, but allows
        other operations to be done elsewhere while paused."""
        d = Deferred()
        self.reactor.callLater(secs,d.callback,'Sleeping')
        return d
        
class serversList(QtGui.QDialog, Ui_ServerList):
    def __init__(self, reactor, parent = None):
        super(serversList, self).__init__(parent)
        self.setupUi(self)
        pos = parent.pos()
        self.move(pos)
        
class advancedApproachSettings(QtGui.QDialog, Ui_advancedApproachSettings):
    def __init__(self,reactor, atto_z_values, JPE_values, parent = None):
        super(advancedApproachSettings, self).__init__(parent)
        self.setupUi(self)
        
        self.pushButton.clicked.connect(self.acceptNewValues)
      
        #Set all the required values
        self.Approach_MeasTime = atto_z_values[0]
        
        self.Atto_Z_Step = atto_z_values[1]
        self.Atto_Z_Points = atto_z_values[2]
        self.Atto_Z_Delay = atto_z_values[3]
        self.Atto_Z_Speed = atto_z_values[4]
        
        self.Atto_Retract_Points = atto_z_values[5]
        self.Atto_Retract_Delay = atto_z_values[6]
        self.Atto_Retract_Speed = atto_z_values[7]
        
        self.Atto_Z_DAC_Out = atto_z_values[8]
      
        self.JPE_Tip_Height = JPE_values[0]
        self.JPE_Module_Address = JPE_values[1]
        
        self.JPE_Approach_Steps = JPE_values[2]
        self.JPE_Approach_Size = JPE_values[3]
        self.JPE_Approach_Freq = JPE_values[4]
        
        self.JPE_Retract_Steps = JPE_values[5]
        self.JPE_Retract_Size = JPE_values[6]
        self.JPE_Retract_Freq = JPE_values[7]
    
        self.Temperature = JPE_values[8]
        
        #Load those values into their appropriate GUI item
        self.loadValues()
        
        self.lineEdit_Atto_Z_Step_Size.editingFinished.connect(self.setAtto_Z_Step_Size)
        self.lineEdit_Atto_Z_Points.editingFinished.connect(self.setAtto_Z_Points)
        self.lineEdit_Atto_Z_Delay.editingFinished.connect(self.setAtto_Z_Delay)
        self.lineEdit_Atto_Z_Speed.editingFinished.connect(self.setAtto_Z_Speed)
        self.lineEdit_Atto_Retract_Points.editingFinished.connect(self.setAtto_Retract_Points)
        self.lineEdit_Atto_Retract_Delay.editingFinished.connect(self.setAtto_Retract_Delay)
        self.lineEdit_Atto_Retract_Speed.editingFinished.connect(self.setAtto_Retract_Speed)
        
        self.lineEdit_Approach_MeasTime.editingFinished.connect(self.setApproach_MeasTime)
        self.comboBox_Atto_Z_DAC_Out.currentIndexChanged.connect(self.setAtto_Z_DAC_Out)
      
        self.lineEdit_Temperature.editingFinished.connect(self.setTemperature)
        self.lineEdit_Tip_Height.editingFinished.connect(self.setJPE_Tip_Height)
        self.comboBox_JPE_Address.currentIndexChanged.connect(self.setJPE_Address)
        
        self.lineEdit_JPE_Approach_Steps.editingFinished.connect(self.setJPE_Approach_Steps)
        self.lineEdit_JPE_Approach_Size.editingFinished.connect(self.setJPE_Approach_Size)
        self.lineEdit_JPE_Approach_Freq.editingFinished.connect(self.setJPE_Approach_Freq)
        
        self.lineEdit_JPE_Retract_Steps.editingFinished.connect(self.setJPE_Retract_Steps)
        self.lineEdit_JPE_Retract_Size.editingFinished.connect(self.setJPE_Retract_Size)
        self.lineEdit_JPE_Retract_Freq.editingFinished.connect(self.setJPE_Retract_Freq)
        
    def loadValues(self):
        self.lineEdit_Atto_Z_Step_Size.setText(formatNum(self.Atto_Z_Step)) 
        self.lineEdit_Atto_Z_Points.setText(formatNum(self.Atto_Z_Points)) 
        self.lineEdit_Atto_Z_Delay.setText(formatNum(self.Atto_Z_Delay)) 
        self.lineEdit_Atto_Z_Speed.setText(formatNum(self.Atto_Z_Speed)) 
        self.lineEdit_Atto_Retract_Points.setText(formatNum(self.Atto_Retract_Points)) 
        self.lineEdit_Atto_Retract_Delay.setText(formatNum(self.Atto_Retract_Delay))
        self.lineEdit_Atto_Retract_Speed.setText(formatNum(self.Atto_Retract_Speed))
        
        self.lineEdit_Approach_MeasTime.setText(formatNum(self.Approach_MeasTime))
        self.comboBox_Atto_Z_DAC_Out.setCurrentIndex(self.Atto_Z_DAC_Out - 1)
        
        self.lineEdit_Temperature.setText(formatNum(self.Temperature))
        self.lineEdit_Tip_Height.setText(formatNum(self.JPE_Tip_Height))
        self.comboBox_JPE_Address.setCurrentIndex(self.JPE_Module_Address - 1)
        
        self.lineEdit_JPE_Approach_Steps.setText(formatNum(self.JPE_Approach_Steps))
        self.lineEdit_JPE_Approach_Size.setText(formatNum(self.JPE_Approach_Size))
        self.lineEdit_JPE_Approach_Freq.setText(formatNum(self.JPE_Approach_Freq))
        
        self.lineEdit_JPE_Retract_Steps.setText(formatNum(self.JPE_Retract_Steps))
        self.lineEdit_JPE_Retract_Size.setText(formatNum(self.JPE_Retract_Size))
        self.lineEdit_JPE_Retract_Freq.setText(formatNum(self.JPE_Retract_Freq))
        
    def setAtto_Z_Step_Size(self):
        val = readNum(str(self.lineEdit_Atto_Z_Step_Size.text()))
        if isinstance(val,float):
            self.Atto_Z_Step = val
            self.Atto_Z_Speed = self.Atto_Z_Step / (self.Atto_Z_Points * self.Atto_Z_Delay)
        self.lineEdit_Atto_Z_Step_Size.setText(formatNum(self.Atto_Z_Step))
        self.lineEdit_Atto_Z_Speed.setText(formatNum(self.Atto_Z_Speed))
        
    def setAtto_Z_Points(self):
        val = readNum(str(self.lineEdit_Atto_Z_Points.text()))
        if isinstance(val,float):
            self.Atto_Z_Points = val
            self.Atto_Z_Speed = self.Atto_Z_Step / (self.Atto_Z_Points * self.Atto_Z_Delay)
        self.lineEdit_Atto_Z_Points.setText(formatNum(self.Atto_Z_Points))
        self.lineEdit_Atto_Z_Speed.setText(formatNum(self.Atto_Z_Speed))
        
    def setAtto_Z_Delay(self):
        val = readNum(str(self.lineEdit_Atto_Z_Delay.text()))
        if isinstance(val,float):
            self.Atto_Z_Delay = val
            self.Atto_Z_Speed = self.Atto_Z_Step / (self.Atto_Z_Points * self.Atto_Z_Delay)
        self.lineEdit_Atto_Z_Delay.setText(formatNum(self.Atto_Z_Delay))
        self.lineEdit_Atto_Z_Speed.setText(formatNum(self.Atto_Z_Speed))
        
    def setAtto_Z_Speed(self):
        val = readNum(str(self.lineEdit_Atto_Z_Speed.text()))
        if isinstance(val,float):
            self.Atto_Z_Speed = val
            self.Atto_Z_Delay = self.Atto_Z_Step / (self.Atto_Z_Points * self.Atto_Z_Speed)
        self.lineEdit_Atto_Z_Speed.setText(formatNum(self.Atto_Z_Speed))
        self.lineEdit_Atto_Z_Delay.setText(formatNum(self.Atto_Z_Delay))
        
    def setAtto_Retract_Delay(self):
        val = readNum(str(self.lineEdit_Atto_Retract_Delay.text()))
        if isinstance(val,float):
            self.Atto_Retract_Delay = val
            self.Atto_Retract_Speed = 24e-6 / (self.Atto_Retract_Points* self.Atto_Retract_Delay)
        self.lineEdit_Atto_Retract_Delay.setText(formatNum(self.Atto_Retract_Delay))
        self.lineEdit_Atto_Retract_Speed.setText(formatNum(self.Atto_Retract_Speed))
        
    def setAtto_Retract_Points(self):
        val = readNum(str(self.lineEdit_Atto_Retract_Points.text()))
        if isinstance(val,float):
            self.Atto_Retract_Points = val
            self.Atto_Retract_Speed = 24e-6 / (self.Atto_Retract_Points* self.Atto_Retract_Delay)
        self.lineEdit_Atto_Retract_Points.setText(formatNum(self.Atto_Retract_Points))
        self.lineEdit_Atto_Retract_Speed.setText(formatNum(self.Atto_Retract_Speed))
        
    def setAtto_Retract_Speed(self):
        val = readNum(str(self.lineEdit_Atto_Retract_Speed.text()))
        if isinstance(val,float):
            self.Atto_Retract_Speed = val
            self.Atto_Retract_Delay = 24e-6 / (self.Atto_Retract_Points* self.Atto_Retract_Speed)
        self.lineEdit_Atto_Retract_Speed.setText(formatNum(self.Atto_Retract_Speed))
        self.lineEdit_Atto_Retract_Delay.setText(formatNum(self.Atto_Retract_Delay))
        
    def setApproach_MeasTime(self):
        val = readNum(str(self.lineEdit_Approach_MeasTime.text()))
        if isinstance(val,float):
            self.Approach_MeasTime = val
        self.lineEdit_Approach_MeasTime.setText(formatNum(self.Approach_MeasTime))
        
    def setAtto_Z_DAC_Out(self):
        self.Atto_Z_DAC_Out = self.comboBox_Atto_Z_DAC_Out.currentIndex() + 1
        
    def setTemperature(self):
        val = readNum(str(self.lineEdit_Temperature.text()))
        if isinstance(val,float):
            self.Temperature = val
        self.lineEdit_Temperature.setText(formatNum(self.Temperature))
    
    def setJPE_Tip_Height(self):
        val = readNum(str(self.lineEdit_Tip_Height.text()))
        if isinstance(val,float):
            self.JPE_Tip_Height = val
        self.lineEdit_Tip_Height.setText(formatNum(self.JPE_Tip_Height))
        
    def setJPE_Address(self):
        self.JPE_Module_Address = self.comboBox_JPE_Address.currentIndex() + 1
    
    def setJPE_Approach_Steps(self):
        val = readNum(str(self.lineEdit_JPE_Approach_Steps.text()))
        if isinstance(val,float):
            self.JPE_Approach_Steps = val
        self.lineEdit_JPE_Approach_Steps.setText(formatNum(self.JPE_Approach_Steps))
        
    def setJPE_Approach_Size(self):
        val = readNum(str(self.lineEdit_JPE_Approach_Size.text()))
        if isinstance(val,float):
            self.JPE_Approach_Size = val
        self.lineEdit_JPE_Approach_Size.setText(formatNum(self.JPE_Approach_Size))
        
    def setJPE_Approach_Freq(self):
        val = readNum(str(self.lineEdit_JPE_Approach_Freq.text()))
        if isinstance(val,float):
            self.JPE_Approach_Freq = val
        self.lineEdit_JPE_Approach_Freq.setText(formatNum(self.JPE_Approach_Freq))
        
    def setJPE_Retract_Steps(self):
        val = readNum(str(self.lineEdit_JPE_Retract_Steps.text()))
        if isinstance(val,float):
            self.JPE_Retract_Steps = val
        self.lineEdit_JPE_Retract_Steps.setText(formatNum(self.JPE_Retract_Steps))
        
    def setJPE_Retract_Size(self):
        val = readNum(str(self.lineEdit_JPE_Retract_Size.text()))
        if isinstance(val,float):
            self.JPE_Retract_Size = val
        self.lineEdit_JPE_Retract_Size.setText(formatNum(self.JPE_Retract_Size))
        
    def setJPE_Retract_Freq(self):
        val = readNum(str(self.lineEdit_JPE_Retract_Freq.text()))
        if isinstance(val,float):
            self.JPE_Retract_Freq = val
        self.lineEdit_JPE_Retract_Freq.setText(formatNum(self.JPE_Retract_Freq))
    
    def acceptNewValues(self):
        self.accept()
        
    def getValues(self):
        atto_z_values = [self.Approach_MeasTime,self.Atto_Z_Step, self.Atto_Z_Points,self.Atto_Z_Delay, 
                        self.Atto_Z_Speed, self.Atto_Retract_Points,  self.Atto_Retract_Delay, self.Atto_Retract_Speed, 
                        self.Atto_Z_DAC_Out]
                      
        JPE_values = [self.JPE_Tip_Height, self.JPE_Module_Address, self.JPE_Approach_Steps, self.JPE_Approach_Size, 
                        self.JPE_Approach_Freq, self.JPE_Retract_Steps, self.JPE_Retract_Size, self.JPE_Retract_Freq, self.Temperature]
        return [atto_z_values, JPE_values]
        
class advancedFeedbackSettings(QtGui.QDialog, Ui_advancedFeedbackSettings):
    def __init__(self,reactor, values,parent = None):
        super(advancedFeedbackSettings, self).__init__(parent)
        self.setupUi(self)
        
        self.pushButton.clicked.connect(self.acceptNewValues)
      
    def acceptNewValues(self):
        self.accept()
        
    def getValues(self):
        return "stuff"
        
class MeasurementSettings(QtGui.QDialog, Ui_MeasurementSettings):
    def __init__(self,reactor, PLL_Values, FT_Values, parent = None, server = None):
        super(MeasurementSettings, self).__init__(parent)
        self.reactor = reactor
        self.setupUi(self)
        
        self.pushButton.clicked.connect(self.acceptNewValues)
        
        self.push_AdvisePID.clicked.connect(self.advisePID)
        
        self.hf = server
            
        self.PLL_TargetBW = PLL_Values[0]
        self.PLL_AdviseMode = PLL_Values[1]
        
        self.PLL_Input  = PLL_Values[2]
        self.PLL_CenterFreq = PLL_Values[3]
        self.PLL_CenterPhase = PLL_Values[4]
        self.PLL_Range = PLL_Values[5]
        
        self.PLL_Harmonic = PLL_Values[6]
        self.PLL_TC = PLL_Values[7]
        self.PLL_FilterBW = PLL_Values[8]
        self.PLL_FilterOrder = PLL_Values[9]
        
        self.PLL_P = PLL_Values[10]
        self.PLL_I = PLL_Values[11]
        self.PLL_D = PLL_Values[12] 
        self.PLL_SimBW = PLL_Values[13]
        self.PLL_PM = PLL_Values[14]
        self.PLL_Rate = PLL_Values[15]

        self.PLL_Output = PLL_Values[16]
        self.PLL_Output_Amp = PLL_Values[17]
        
        self.FT_Input = FT_Values[0]
        self.FT_Frequency = FT_Values[1]
        self.FT_Output = FT_Values[2]
        self.FT_Amplitude = FT_Values[3]
        
        self.F_Demod = FT_Values[4]
        self.F_Harmonic = FT_Values[5]
        self.F_TC = FT_Values[6]
        
        self.T_Demod = FT_Values[7]
        self.T_Harmonic = FT_Values[8]
        self.T_TC = FT_Values[9]
        
        self.lineEdit_TargetBW.editingFinished.connect(self.setPLL_TargetBW)
        self.lineEdit_PLL_Range.editingFinished.connect(self.setPLL_Range)
        self.lineEdit_PLL_TC.editingFinished.connect(self.setPLL_TC)
        self.lineEdit_PLL_FilterBW.editingFinished.connect(self.setPLL_FilterBW)
        self.lineEdit_PLL_P.editingFinished.connect(self.setPLL_P)
        self.lineEdit_PLL_I.editingFinished.connect(self.setPLL_I)
        self.lineEdit_PLL_D.editingFinished.connect(self.setPLL_D)
        self.lineEdit_PLL_Rate.editingFinished.connect(self.setPLL_Rate)
        
        self.comboBox_PLL_Advise.currentIndexChanged.connect(self.setPLL_AdviseMode)
        self.comboBox_PLL_FilterOrder.currentIndexChanged.connect(self.setPLL_FilterOrder)
        self.comboBox_PLL_Harmonic.currentIndexChanged.connect(self.setPLL_Harmonic)
        self.comboBox_PLL_Input.currentIndexChanged.connect(self.setPLL_Input)
        
        self.lineEdit_FT_Freq.editingFinished.connect(self.setFT_Freq)
        self.lineEdit_FT_Amp.editingFinished.connect(self.setFT_Amp)
        
        self.comboBox_FT_Input.currentIndexChanged.connect(self.setFT_Input)
        self.comboBox_FT_Output.currentIndexChanged.connect(self.setFT_Output)
        
        self.lineEdit_F_TC.editingFinished.connect(self.setF_TC)
        
        self.comboBox_F_Demod.currentIndexChanged.connect(self.setF_Demod)
        self.comboBox_F_Harmonic.currentIndexChanged.connect(self.setF_Harmonic)
        
        self.lineEdit_T_TC.editingFinished.connect(self.setT_TC)
        
        self.comboBox_T_Demod.currentIndexChanged.connect(self.setT_Demod)
        self.comboBox_T_Harmonic.currentIndexChanged.connect(self.setT_Harmonic)
        
        self.lineEdit_PLL_Amplitude.editingFinished.connect(self.setPLL_Output_Amplitude)
        self.comboBox_PLL_Output.currentIndexChanged.connect(self.setPLL_Output)

        self.loadValues()
        self.createLoadingColors()
        
    def loadValues(self):
        self.lineEdit_TargetBW.setText(formatNum(self.PLL_TargetBW))
        self.comboBox_PLL_Advise.setCurrentIndex(self.PLL_AdviseMode)
        self.comboBox_PLL_Input.setCurrentIndex(self.PLL_Input - 1)
        
        if self.PLL_CenterFreq is not None:
            self.lineEdit_PLL_CenterFreq.setText(formatNum(self.PLL_CenterFreq))
        else:
            self.lineEdit_PLL_CenterFreq.setText('None')
        if self.PLL_CenterPhase is not None:
            self.lineEdit_PLL_phaseSetPoint.setText(formatNum(self.PLL_CenterPhase))
        else:
            self.lineEdit_PLL_phaseSetPoint.setText('None')
        self.lineEdit_PLL_Range.setText(formatNum(self.PLL_Range))
        
        self.comboBox_PLL_Harmonic.setCurrentIndex(self.PLL_Harmonic -1)
        self.hf.set_advisor_harmonic(self.PLL_Harmonic)
        
        self.lineEdit_PLL_TC.setText(formatNum(self.PLL_TC))
        self.lineEdit_PLL_FilterBW.setText(formatNum(self.PLL_FilterBW))
        self.hf.set_advisor_tc(self.PLL_TC)
        
        self.comboBox_PLL_FilterOrder.setCurrentIndex(self.PLL_FilterOrder -1)
        self.hf.set_advisor_filterorder(self.PLL_FilterOrder)
        
        self.lineEdit_PLL_P.setText(formatNum(self.PLL_P, 4))
        self.hf.set_advisor_p(self.PLL_P)
        self.lineEdit_PLL_I.setText(formatNum(self.PLL_I, 4))
        self.hf.set_advisor_i(self.PLL_I)
        self.lineEdit_PLL_D.setText(formatNum(self.PLL_D, 4))
        self.hf.set_advisor_d(self.PLL_D)
        self.lineEdit_PLL_SimBW.setText(formatNum(self.PLL_SimBW, 4))
        self.lineEdit_PLL_PM.setText(formatNum(self.PLL_PM, 4))
        self.lineEdit_PLL_Rate.setText(formatNum(self.PLL_Rate, 4))
        
        
        self.comboBox_FT_Input.setCurrentIndex(self.FT_Input-1)
        self.comboBox_FT_Output.setCurrentIndex(self.FT_Output-1)
        
        self.lineEdit_FT_Freq.setText(formatNum(self.FT_Frequency))

        if self.FT_Output == 3:
            self.lineEdit_FT_Amp.setText('N/A')
            self.lineEdit_FT_Amp.setEnabled(False)
        else:
            self.lineEdit_FT_Amp.setText(formatNum(self.FT_Amplitude))
            self.lineEdit_FT_Amp.setEnabled(True)
            
        self.comboBox_F_Demod.setCurrentIndex(self.F_Demod-1)
        self.comboBox_F_Harmonic.setCurrentIndex(self.F_Harmonic-1)
        self.lineEdit_F_TC.setText(formatNum(self.F_TC))
        
        self.comboBox_T_Demod.setCurrentIndex(self.T_Demod-1)
        self.comboBox_T_Harmonic.setCurrentIndex(self.T_Harmonic-1)
        self.lineEdit_T_TC.setText(formatNum(self.T_TC))

        self.lineEdit_PLL_Amplitude.setText(formatNum(self.PLL_Output_Amp))
        self.comboBox_PLL_Output.setCurrentIndex(self.PLL_Output - 1)
        
    #Creates a list of stylesheets with a gradient of grey to black. This
    #will be used when the advisePID button is pressed to indicate that
    #it is processing. 
    def createLoadingColors(self):
        base_sheet = '''#push_AdvisePID{
                        background-color: rgb(230,230,230);
                        border: 2px solid rgb(210,210,210);
                        border-radius: 2px;
                        }'''
        self.sheets = []
        for i in range(0,40):
            new_border = 210 - i*5
            new_background = 230 - i*5
            new_sheet = base_sheet.replace('210',str(new_border))
            new_sheet = new_sheet.replace('230',str(new_background))
            self.sheets.append(new_sheet)
        for i in range(0,40):
            new_border = 20 + i*5
            new_background = 40 + i*5
            new_sheet = base_sheet.replace('210',str(new_border))
            new_sheet = new_sheet.replace('230',str(new_background))
            self.sheets.append(new_sheet)
        
    def setPLL_TargetBW(self):
        new_target = str(self.lineEdit_TargetBW.text())
        val = readNum(new_target)
        if isinstance(val,float):
            self.PLL_TargetBW = val
        self.lineEdit_TargetBW.setText(formatNum(self.PLL_TargetBW))
      
    def setPLL_Range(self):
        new_range = str(self.lineEdit_PLL_Range.text())
        val = readNum(new_range)
        if isinstance(val,float):
            self.PLL_Range = val
        self.lineEdit_PLL_Range.setText(formatNum(self.PLL_Range))
        
    @inlineCallbacks
    def setPLL_Rate(self, c = None):
        new_rate = str(self.lineEdit_PLL_Rate.text())
        val = readNum(new_rate)
        if isinstance(val,float):
            self.PLL_Rate = val
            yield self.hf.set_advisor_rate(self.PLL_Rate)
            yield self.updateSimulation()
        self.lineEdit_PLL_Range.setText(formatNum(self.PLL_Range))
    
    @inlineCallbacks
    def setPLL_TC(self, c = None):
        new_TC = str(self.lineEdit_PLL_TC.text())
        val = readNum(new_TC)
        if isinstance(val,float):
            self.PLL_TC = val
            self.PLL_FilterBW = 0.0692291283 / val
            yield self.hf.set_advisor_tc(self.PLL_TC)
            yield self.updateSimulation()
        self.lineEdit_PLL_TC.setText(formatNum(self.PLL_TC))
        self.lineEdit_PLL_FilterBW.setText(formatNum(self.PLL_FilterBW))
    
    @inlineCallbacks
    def setPLL_FilterBW(self, c = None):
        new_filterBW = str(self.lineEdit_PLL_FilterBW.text())
        val = readNum(new_filterBW)
        if isinstance(val,float):
            self.PLL_FilterBW = val
            self.PLL_TC = 0.0692291283 / val
            yield self.hf.set_advisor_tc(self.PLL_TC)
            yield self.updateSimulation()
        self.lineEdit_PLL_TC.setText(formatNum(self.PLL_TC))
        self.lineEdit_PLL_FilterBW.setText(formatNum(self.PLL_FilterBW))
    
    @inlineCallbacks
    def setPLL_P(self, c = None):
        new_P = str(self.lineEdit_PLL_P.text())
        val = readNum(new_P)
        if isinstance(val,float):
            self.PLL_P = val
            yield self.hf.set_advisor_p(self.PLL_P)
            yield self.updateSimulation()
        self.lineEdit_PLL_P.setText(formatNum(self.PLL_P))
        
    @inlineCallbacks
    def setPLL_I(self, c = None):
        new_I = str(self.lineEdit_PLL_I.text())
        val = readNum(new_I)
        if isinstance(val,float):
            self.PLL_I = val
            yield self.hf.set_advisor_i(self.PLL_I)
            yield self.updateSimulation()
        self.lineEdit_PLL_I.setText(formatNum(self.PLL_I))
        
    @inlineCallbacks
    def setPLL_D(self, c = None):
        new_D = str(self.lineEdit_PLL_D.text())
        val = readNum(new_D)
        if isinstance(val,float):
            self.PLL_D = val
            yield self.hf.set_advisor_d(self.PLL_D)
            yield self.updateSimulation()
        self.lineEdit_PLL_D.setText(formatNum(self.PLL_D))
        
    def setPLL_Input(self):
        self.PLL_Input = self.comboBox_PLL_Input.currentIndex() + 1

    def setPLL_Output(self):
        self.PLL_Output = self.comboBox_PLL_Output.currentIndex() + 1
        
    def setPLL_Output_Amplitude(self):
        val = readNum(str(self.lineEdit_PLL_Amplitude.text()))
        if isinstance(val,float):
            self.PLL_Output_Amp = val
        self.lineEdit_PLL_Amplitude.setText(formatNum(self.PLL_Output_Amp))

    @inlineCallbacks
    def setPLL_Harmonic(self, c = None):
        self.PLL_Harmonic = self.comboBox_PLL_Harmonic.currentIndex() + 1
        yield self.hf.set_advisor_harmonic(self.PLL_Harmonic)
        yield self.updateSimulation()
        
    @inlineCallbacks
    def setPLL_FilterOrder(self, c = None):
        self.PLL_FilterOrder = self.comboBox_PLL_FilterOrder.currentIndex() + 1
        yield self.hf.set_advisor_filterorder(self.PLL_FilterOrder)
        yield self.updateSimulation()
        
    def setPLL_AdviseMode(self):
        self.PLL_AdviseMode = self.comboBox_PLL_Advise.currentIndex()
        
    def setFT_Freq(self):
        new_freq = str(self.lineEdit_FT_Freq.text())
        val = readNum(new_freq)
        if isinstance(val,float):
            self.FT_Frequency = val
        self.lineEdit_FT_Freq.setText(formatNum(self.FT_Frequency))
        
    def setFT_Amp(self):
        val = readNum(str(self.lineEdit_FT_Amp.text()))
        if isinstance(val,float):
            self.FT_Amplitude = val
        self.lineEdit_FT_Amp.setText(formatNum(self.FT_Amplitude))
        
    def setFT_Input(self):
        self.FT_Input = self.comboBox_FT_Input.currentIndex() + 1
        
    def setFT_Output(self):
        self.FT_Output = self.comboBox_FT_Output.currentIndex() + 1
        if self.FT_Output == 3:
            self.lineEdit_FT_Amp.setText('N/A')
            self.lineEdit_FT_Amp.setEnabled(False)
        else:
            self.lineEdit_FT_Amp.setEnabled(True)
            self.lineEdit_FT_Amp.setText(formatNum(self.FT_Amplitude))
            
    def setF_Demod(self):
        self.F_Demod = self.comboBox_F_Demod.currentIndex() + 1
        
    def setF_Harmonic(self):
        self.F_Harmonic = self.comboBox_F_Harmonic.currentIndex() + 1
        
    def setF_TC(self):
        val = readNum(str(self.lineEdit_F_TC.text()))
        if isinstance(val,float):
            self.F_TC = val
        self.lineEdit_F_TC.setText(formatNum(self.F_TC))
        
    def setT_Demod(self):
        self.T_Demod = self.comboBox_T_Demod.currentIndex() + 1
        
    def setT_Harmonic(self):
        self.T_Harmonic = self.comboBox_T_Harmonic.currentIndex() + 1
        
    def setT_TC(self):
        val = readNum(str(self.lineEdit_T_TC.text()))
        if isinstance(val,float):
            self.T_TC = val
        self.lineEdit_T_TC.setText(formatNum(self.T_TC))
    
    @inlineCallbacks
    def updateSimulation(self):
        try:
            calculating = True
            print 'Waiting for calculation'
            yield self.sleep(0.25)
            while calculating:
                calculating = yield self.hf.get_advisor_calc()
                print calculating
            print 'done calaculating'
            pm = yield self.hf.get_advisor_pm()
            bw = yield self.hf.get_advisor_simbw()
            self.PLL_PM = pm
            self.PLL_SimBW = bw
            self.lineEdit_PLL_PM.setText(formatNum(self.PLL_PM))
            self.lineEdit_PLL_SimBW.setText(formatNum(self.PLL_SimBW))
        except Exception as inst:
            print inst
        
    def acceptNewValues(self):
        self.accept()
        
    def advisePID(self):
        try:
            self.PID_advice = False
            self.computePIDParameters()
            self.displayCalculatingGraphics()
        except Exception as inst:
            print inst
        
    @inlineCallbacks
    def computePIDParameters(self, c = None):
        try:
            self.PID_advice = yield self.hf.advise_pll_pid(1, self.PLL_TargetBW,self.PLL_AdviseMode)
            self.PLL_P = yield self.hf.get_advisor_p()
            self.PLL_I = yield self.hf.get_advisor_i()
            self.PLL_D = yield self.hf.get_advisor_d()
            self.PLL_SimBW = yield self.hf.get_advisor_simbw()
            self.PLL_Rate  = yield self.hf.get_advisor_rate()
            self.PLL_PM = yield self.hf.get_advisor_pm()
            self.PLL_TC = yield self.hf.get_advisor_tc()
            self.PLL_FilterBW = 0.0692291283 / self.PLL_TC

            self.lineEdit_PLL_P.setText(formatNum(self.PLL_P))
            self.lineEdit_PLL_I.setText(formatNum(self.PLL_I))
            self.lineEdit_PLL_D.setText(formatNum(self.PLL_D))
            self.lineEdit_PLL_PM.setText(formatNum(self.PLL_PM))
            self.lineEdit_PLL_SimBW.setText(formatNum(self.PLL_SimBW))
            self.lineEdit_PLL_FilterBW.setText(formatNum(self.PLL_FilterBW))
            self.lineEdit_PLL_Rate.setText(formatNum(self.PLL_Rate))
            self.lineEdit_PLL_TC.setText(formatNum(self.PLL_TC))

            #self.PID_advice = 'Pasta'
        except Exception as inst:
            print inst
        
    @inlineCallbacks
    def displayCalculatingGraphics(self, c = None):
        try:
            i = 0
            while not self.PID_advice:
                self.push_AdvisePID.setStyleSheet(self.sheets[i])
                yield self.sleep(0.025)
                i = (i+1)%80
            self.push_AdvisePID.setStyleSheet(self.sheets[0])
        except Exception as inst:
            print inst

    def getValues(self):
        PLL_Values = [self.PLL_TargetBW, self.PLL_AdviseMode, self.PLL_Input, self.PLL_CenterFreq, self.PLL_CenterPhase, 
                        self.PLL_Range, self.PLL_Harmonic, self.PLL_TC, self.PLL_FilterBW, self.PLL_FilterOrder, 
                        self.PLL_P, self.PLL_I, self.PLL_D, self.PLL_SimBW, self.PLL_PM, self.PLL_Rate, self.PLL_Output,
                        self.PLL_Output_Amp]   
        FT_Values = [self.FT_Input, self.FT_Frequency, self.FT_Output, self.FT_Amplitude, self.F_Demod, 
                        self.F_Harmonic, self.F_TC, self.T_Demod, self.T_Harmonic, self.T_TC]
        return PLL_Values, FT_Values
        
    def sleep(self,secs):
        """Asynchronous compatible sleep command. Sleeps for given time in seconds, but allows
        other operations to be done elsewhere while paused."""
        d = Deferred()
        self.reactor.callLater(secs,d.callback,'Sleeping')
        return d
        
class MySlider(QtGui.QSlider):
    logValueChanged = QtCore.pyqtSignal(float)
    #Shitty programming. Only looks good for horizontal sliders with length 400 and thickness 70. 
    def __init__(self, parent=None): 
        self.tickPos = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
        self.numPos = [1, 2, 3, 4, 5, 6, 7, 8, 9, 10]
        super(MySlider, self).__init__(QtCore.Qt.Horizontal, parent)
 
        self.valueChanged.connect(self.emitLogValue)
        self.valueChangedManually = False
        
    def paintEvent(self, event):
        """Paint log scale ticks"""
        super(MySlider, self).paintEvent(event)
        qp = QtGui.QPainter(self)
        pen = QtGui.QPen()
        pen.setWidth(1)
        pen.setColor(QtGui.QColor(168,168,168))
 
        qp.setPen(pen)
        font = QtGui.QFont('Times', 10)
        font_y_offset = font.pointSize()/2
        qp.setFont(font)
        size = self.size()
        contents = self.contentsRect()
        width = contents.width()
        height = contents.height()
        y = contents.y()
        max = np.log10(self.tickPos[-1])
        min = np.log10(self.tickPos[0])
        lower_padding = 8
        upper_padding = 16
        for val in self.tickPos:
            log_val = np.log10(val)
            x_val = round( (log_val-min)* (width-upper_padding) / (max-min)) + lower_padding
            if val in self.numPos:
                pen.setColor(QtGui.QColor(95,107,166))
                pen.setWidth(2)
                qp.setPen(pen)
                qp.drawLine(x_val , y + 45,  x_val, y+50)
                pen.setColor(QtGui.QColor(168,168,168))
                pen.setWidth(1)
                qp.setPen(pen)
                #text = '{0:2}'.format(val)
                text = formatNum(val)
                x_offset = float(len(text)*font.pointSize()/(3))
                qp.drawText(x_val - x_offset, y + 58 + font_y_offset,text)
            else:
                qp.drawLine(x_val , y + 45,  x_val, y+50)
    
    def setTickPos(self, ticks):
        self.tickPos = ticks
        
    def setNumPos(self, nums):
        self.numPos = nums
        
    def emitLogValue(self, val):
        if not self.valueChangedManually:
            min = float(self.minimum())
            max = float(self.maximum())
            val = self.tickPos[0]*10**(np.log10(self.tickPos[-1]/self.tickPos[0])*(val-min)/max)
            self.logValueChanged.emit(val)
        else:
            self.valueChangedManually = False
            
    def setPosition(self,val):
        min = float(self.minimum())
        max = float(self.maximum())
        val = min + np.log10(val/self.tickPos[0])*max/np.log10(self.tickPos[-1]/self.tickPos[0])
        self.valueChangedManually = True
        self.setSliderPosition(int(round(val)))
            
def formatNum(val, decimal_values = 2):
    if val != val:
        return 'nan'
        
    string = '%e'%val
    num  = float(string[0:-4])
    exp = int(string[-3:])
    if exp < -6:
        diff = exp + 9
        num = num * 10**diff
        if num - int(num) == 0:
            num = int(num)
        else: 
            num = round(num,decimal_values)
        string = str(num)+'n'
    elif exp < -3:
        diff = exp + 6
        num = num * 10**diff
        if num - int(num) == 0:
            num = int(num)
        else: 
            num = round(num,decimal_values)
        string = str(num)+'u'
    elif exp < 0:
        diff = exp + 3
        num = num * 10**diff
        if num - int(num) == 0:
            num = int(num)
        else: 
            num = round(num,decimal_values)
        string = str(num)+'m'
    elif exp < 3:
        if val - int(val) == 0:
            val = int(val)
        else: 
            val = round(val,decimal_values)
        string = str(val)
    elif exp < 6:
        diff = exp - 3
        num = num * 10**diff
        if num - int(num) == 0:
            num = int(num)
        else: 
            num = round(num,decimal_values)
        string = str(num)+'k'
    elif exp < 9:
        diff = exp - 6
        num = num * 10**diff
        if num - int(num) == 0:
            num = int(num)
        else: 
            num = round(num,decimal_values)
        string = str(num)+'M'
    elif exp < 12:
        diff = exp - 9
        num = num * 10**diff
        if num - int(num) == 0:
            num = int(num)
        else: 
            num = round(num,decimal_values)
        string = str(num)+'G'
    return string
    
def readNum(string):
    try:
        val = float(string)
    except:
        exp = string[-1]
        if exp == 'm':
            exp = 1e-3
        if exp == 'u':
            exp = 1e-6
        if exp == 'n':
            exp = 1e-9
        if exp == 'k':
            exp = 1e3
        if exp == 'M':
            exp = 1e6
        if exp == 'G':
            exp = 1e9
        try:
            val = float(string[0:-1])*exp
        except: 
            return 'Incorrect Format'
    return val
    