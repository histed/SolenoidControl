# 'Reward window':  Control solenoid for drain and cleaning purposes
#
#  Adapted 12/28/10 by histed
#  Requires the Enthought Python distribution (Traits)




#! The imports
#!-------------
#!
#! The MPLFigureEditor is imported from last example.
#
#
#


from threading import Thread
from time import sleep, clock
from enthought.traits.api import *
from enthought.traits.ui.api import View, Item, Group, \
        HSplit, Handler
from enthought.traits.ui.menu import NoButtons
from mpl_figure_editor import MPLFigureEditor
from matplotlib.figure import Figure
from scipy import *
import wx

#! User interface objects
#!------------------------
#!
#! These objects store information for the program to interact with the
#! user via traitsUI.

class ContOpenTraits(HasTraits):
    """ Object that contains the parameters that control the experiment, 
        modified by the user.
    """
    openTimeS = Float(60, label="Open time (s)", desc='open time in seconds')


class PulsedOpenTraits(HasTraits):
    """ Object used to display the results.
    """
    totalTimeS = Float(60, label="Total time of all pulses (s)", desc='total')
    pulseTimeS = Float(0.5, label="Pulse time (s)")
    pulsePeriodS = Float(1, label="Pulse period (s)")
    
    view = View( Item('totalTimeS'),
                 Item('pulseTimeS'), 
                 Item('pulsePeriodS'),
               )

#!
#! The camera object also is a real object, and not only a data
#! structure: it has a method to acquire an image (or in our case
#! simulate acquiring), using its attributes as parameters for the
#! acquisition.
#!

#! Threads and flow control
#!--------------------------
#!
#! There are three threads in this application:
#! 
#!  * The GUI event loop, the only thread running at the start of the program.
#!
#!  * The acquisition thread, started through the GUI. This thread is an
#!    infinite loop that waits for the camera to be triggered, retrieves the 
#!    images, displays them, and spawns the processing thread for each image
#!    recieved.
#!
#!  * The processing thread, started by the acquisition thread. This thread
#!    is responsible for the numerical intensive work of the application.
#!    it processes the data and displays the results. It dies when it is done.
#!    One processing thread runs per shot acquired on the camera, but to avoid
#!    accumulation of threads in the case that the processing takes longer than
#!    the time lapse between two images, the acquisition thread checks that the
#!    processing thread is done before spawning a new one.
#! 


class SolenoidThread(Thread):
    """ Worker thread that handles the solenoid
    """

    # parameters used to talk to the main thread
    wantsAbort = False
    pulseTimeS = None
    totalTimeS = None
    pulsePeriodS = None

    # internal variables
    _openStillLeft = 0


    def run(self):
        """ main thread; assumes parameters are set up
        """
        stT = clock()

        assert(self.pulseTimeS > 0)

        pulseN = 0
        while (stT - clock()) < self.totalTimeS:

            pulseStT = clock()

            if self.wantsAbort:
                self.wantsAbort = False;
                break

            # do actual pulse
            self.doSinglePulse(self.pulseTimeS)
            pulseN += 1
            self.display('pulse %d' % pulseN)
            sleep( self.pulsePeriodS - (clock()-pulseStT) )

        
            


    def doSinglePulse(self, openTimeS):
        self.display("Opening for %3.1fs" % openTimeS)
        # sleep in 1 s chunks so we can abort
        self._openStillLeft = openTimeS
        while self._openStillLeft > 0 and self.wantsAbort == False:
            if self._openStillLeft > 1:
                sleep(1)
                self._openStillLeft = self._openStillLeft-1
                self.display(str(self._openStillLeft))
            else:
                sleep(self._openStillLeft);
                self._openStillLeft = 0

        self.closeIt()

    def setupSinglePulse(self, pulseTimeS):
        self.pulseTimeS = pulseTimeS
        self.totalTimeS = pulseTimeS
        self.pulsePeriodS = pulseTimeS

    def setupPulseTrain(self, pulseTimeS, totalTimeS, pulsePeriodS):
        self.pulseTimeS = pulseTimeS
        self.totalTimeS = totalTimeS
        self.pulsePeriodS = pulsePeriodS

    def closeIt(self):
        """ Close solenoid """
        self.display("Closed")

#! The GUI elements
#!------------------
#!
#! The GUI of this application is separated in two (and thus created by a
#! sub-class of *SplitApplicationWindow*).
#!
#! On the left a plotting area, made of an MPL figure, and its editor, displays
#! the images acquired by the camera.
#!
#! On the right a panel hosts the `TraitsUI` representation of a *ControlPanel*
#! object. This object is mainly a container for our other objects, but it also
#! has an *Button* for starting or stopping the acquisition, and a string 
#! (represented by a textbox) to display informations on the acquisition
#! process. The view attribute is tweaked to produce a pleasant and usable
#! dialog. Tabs are used as it help the display to be light and clear.
#!

class ControlPanel(HasTraits):
    """ This object is the core of the traitsUI interface. Its view is
        the right panel of the application, and it hosts the method for
        interaction between the objects and the GUI.
    """
    contopen = Instance(ContOpenTraits, ())
    figure = Instance(Figure)
    pulsedopen = Instance(PulsedOpenTraits, ())
    cont_button = Button("Open Solenoid")
    pulsed_button = Button("Start")
    stop_button = Button("Stop")
    results_string =  String()
    solenoid_thread = Instance(SolenoidThread)
    view = View(Group(
        Group(
            Group(
                Item('contopen', style='custom', show_label=False),
                Item('cont_button', label="Open Solenoid", full_size=False),
                label="Continuous open", orientation='vertical', show_border=True),
            
            Group(
                Item('pulsedopen', style='custom', show_label=False),
                Item('pulsed_button', label="Start"),
                label="Pulsed open",show_border=True),
            Group(
                Item('stop_button', label="Stop all and close solenoid"),
                ),
            Group(
                Item('results_string',show_label=False, 
                     springy=True, style='custom'),),
            label='Solenoid control', dock="tab"),
        layout='tabbed'))

    def closeSolenoidIfOpen(self):
        """ also kills any pulse train running """
        if self.solenoid_thread and self.solenoid_thread.isAlive():
            self.solenoid_thread.wantsAbort = True
            sleep(1);
            self.add_line('Closed forcibly')

    def _stop_button_fired(self):
        self.closeSolenoidIfOpen()
    
    def _cont_button_fired(self):
        """ Callback """
        self.closeSolenoidIfOpen()

        self.solenoid_thread = SolenoidThread()
        self.solenoid_thread.display = self.add_line
        self.solenoid_thread.setupSinglePulse(self.contopen.openTimeS)
        self.solenoid_thread.start()
        
    def _pulsed_button_fired(self):
        """ Callback """
        self.closeSolenoidIfOpen()

        self.solenoid_thread = SolenoidThread()
        self.solenoid_thread.display = self.add_line
        self.solenoid_thread.setupPulseTrain(self.pulsedopen.pulseTimeS,
                                             self.pulsedopen.totalTimeS,
                                             self.pulsedopen.pulsePeriodS)
        self.solenoid_thread.start()

    
    def add_line(self, string):
        """ Adds a line to the textbox display.
        """
        self.results_string = (string + "\n" + self.results_string)[0:1000]

    def image_show(self, image):
        """ Plots an image on the canvas in a thread safe way.
        """
        self.figure.axes[0].images=[]
        self.figure.axes[0].imshow(image, aspect='auto')
        wx.CallAfter(self.figure.canvas.draw)

class MainWindowHandler(Handler):
    def close(self, info, is_OK):
        if ( info.object.panel.solenoid_thread 
                        and info.object.panel.solenoid_thread.isAlive() ):
            info.object.panel.solenoid_thread.wants_abort = True
            while info.object.panel.solenoid_thread.isAlive():
                sleep(0.1)
            wx.Yield()
        return True


class MainWindow(HasTraits):
    """ The main window, here go the instructions to create and destroy
        the application.
    """
    figure = Instance(Figure)

    panel = Instance(ControlPanel)

    def _figure_default(self):
        figure = Figure()
        figure.add_axes([0.05, 0.04, 0.9, 0.92])
        return figure

    def _panel_default(self):
        return ControlPanel(figure=self.figure)

    view = View(HSplit(  Item('figure',  editor=MPLFigureEditor(),
                                                        dock='vertical'),
                        Item('panel', style="custom"),
                    show_labels=False, 
                    ),
                resizable=True, 
                height=0.75, width=0.75,
                handler=MainWindowHandler(),
                buttons=NoButtons)
                

if __name__ == '__main__':
    MainWindow().configure_traits()
