# Stroop Task Suite for PsychoPy  
## High- and Low-Contrast Versions with LSL Support  

**Developer**: Rasmus Åberg Lindell  
**Year**: 2024  
**License**: CC-BY-4.0
Contact: rassiver@hotmail.com  

For citation purposes, please use:  
"Custom Stroop implementation (Lindell, 2024) with LSL markers."

Description
PsychoPy-based Stroop tasks with integrated LabStreamingLayer (LSL) for neurophysiology synchronization:

High Contrast (HC): Black background with saturated colors

Low Contrast (LC): Gray or Black background with desaturated colors

Configured for compatibility with EEG/fNIRS systems (e.g., NIRx, BrainVision).
---------------------------------------------------------------------------------
Stroop Task Variants
Paradigm Name	Contrast	Key Features			Trials	Files
Standard	HC or LC	- Performance feedback (✓/✗)	8/blk	Stroop_feedback_HC/LC.py
				- Fixed 500ms ITI
		
Randomized ITI	HC or LC	- No feedback			8/blk	Stroop_HC/LC_rd_ITI.py
				- Jittered ITI (800-1200ms)
				- fMRI/EEG optimized
		
Extended	HC or LC	- Mixed block lengths (8 & 15)	92 tot	Stroop_HC/LC_rd_ITI-long.py
				- Longer neutral periods
		
Merged Design	Both		- Combined HC/LC		184 tot	Merge_HC_LC_rd_BLOCK.py
				- Smart block sequencing
				- Dual contrast analysis
		
Key:
HC = High Contrast, LC = Low Contrast, blk = block, tot = total
----------------------------------------------------------------------------------
Feature Comparison:

Feature			Standard	Random ITI	Extended	Merged
Feedback		✓		✗		✗		✗
ITI Type		Fixed		Random		Random		Random
Block Lengths		8		8		8 & 15		8 & 15
Contrasts per Run	Single		Single		Single		Both
Best For		Behavior	EEG/fMRI	fNIRS		Multi-modal
----------------------------------------------------------------------------------

------------------

Dependencies
python
pylsl >= 1.16.1  # LSL communication
pandas >= 1.3.0  # Data handling
numpy >= 1.21.0  # Numerical operations
------------------

Usage
Run in PsychoPy:

LSL Integration:

Stream name: StroopMarkers/Stroopmarkers2

Data Output:

Raw trial-by-trial data (.csv)

Summary statistics (accuracy, RTs, Stroop effect)

bibtex

@misc{Lindell_StroopLSL,
  author = {Lindell, Rasmus Åberg},
  year = {2024},
  title = {Dual-Contrast Stroop Task Suite},
  howpublished = {Available by request from author},
  note = {License: CC-BY-4.0}
}

APA
Lindell, R. Å. (2024).  
Dual-contrast Stroop task scripts with LabStreamingLayer integration [Unpublished computer software]. 
