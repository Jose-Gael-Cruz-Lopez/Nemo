import cv2
import numpy as np
import pytest

from apps.vision.reeftrace_vision.calibration import fit_homography, project
from apps.vision.reeftrace_vision.tracking import SingleTokenTracker, detect_red, flow_samples


def calibration():
    return fit_homography([[0,0],[300,0],[300,200],[0,200]], [[0,0],[30,0],[30,20],[0,20]],
                          [[50,50],[100,100],[250,150]], [[5,5],[10,10],[25,15]], max_error_cm=.1)


def test_water_plane_mapping_uses_separate_validation_points():
    result = calibration()
    assert result['approved'] and result['max_error_cm'] < 1e-8
    assert np.allclose(project(result['homography_image_to_cm'], [[150,50]]), [[15,5]])


def test_wrong_validation_geometry_is_not_approved():
    result = fit_homography([[0,0],[10,0],[10,10],[0,10]], [[0,0],[10,0],[10,10],[0,10]],
                           [[2,2],[3,4],[5,5]], [[2,2],[7,4],[5,5]], max_error_cm=.1)
    assert not result['approved'] and result['max_error_cm'] > 3


def test_fitting_points_cannot_be_reused_as_validation():
    with pytest.raises(ValueError, match='repeat'):
        fit_homography([[0,0],[10,0],[10,10],[0,10]], [[0,0],[10,0],[10,10],[0,10]],
                       [[0,0],[3,4],[5,5]], [[0,0],[3,4],[5,5]])


def test_collinear_calibration_rejected():
    with pytest.raises(ValueError, match='collinear'):
        fit_homography([[0,0],[1,0],[2,0],[3,0]], [[0,0],[1,0],[2,0],[3,0]],
                       [[5,1],[6,1],[7,1]], [[5,1],[6,1],[7,1]])


def test_red_hue_wrap_and_multiple_tokens_are_ambiguous():
    hsv = np.zeros((200,300,3), np.uint8)
    cv2.rectangle(hsv,(30,40),(40,50),(178,240,200),-1)
    image = cv2.cvtColor(hsv,cv2.COLOR_HSV2BGR)
    points=detect_red(image)
    assert len(points)==1 and abs(points[0]['pixel_x']-35)<.1
    cv2.rectangle(image,(100,40),(110,50),(0,0,255),-1)
    tracker=SingleTokenTracker()
    assert tracker.update(detect_red(image),0,calibration())['reason']=='MULTIPLE_TOKENS'


def test_track_gap_starts_new_identity_without_interpolation():
    tracker=SingleTokenTracker(max_gap_s=.3)
    d=[{'pixel_x':50,'pixel_y':50}]
    first=tracker.update(d,0,calibration())
    missed=tracker.update([],0.1,calibration())
    last=tracker.update(d,0.2,calibration())
    assert not missed['observed'] and first['track_id']!=last['track_id']
    assert flow_samples([first,missed,last])==[]


def test_nonoverlapping_finite_difference_velocity():
    track=[{'t_s':i*.1,'x_cm':i*.2,'y_cm':0,'observed':True,'track_id':'one'} for i in range(4)]
    samples=flow_samples(track)
    assert len(samples)==2
    assert all(abs(s['vx_cm_s']-2)<1e-8 for s in samples)
