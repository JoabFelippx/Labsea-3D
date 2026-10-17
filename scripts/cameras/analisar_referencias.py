"""Triangulação, reprojeção e planos de diagnóstico a partir de anotações ROI.

Não detecta objetos automaticamente. Os pontos manuais ficam em landmarks.json.
Planos elevados servem apenas a objetos que realmente pertencem àquela altura.
"""
import argparse
import json
from pathlib import Path

import cv2
import numpy as np

ROOT=Path(__file__).resolve().parents[2]


def load_calibrations():
    result={}
    for i in range(1,5):
        with np.load(ROOT/f'dados/calibracao/calib_rt{i}.npz',allow_pickle=False) as f:
            result[i]={key:f[key].copy() for key in ('nK','rt','rt_inv','roi')}
    return result


def ray(uv, calib):
    pixel=np.r_[np.asarray(uv)+calib['roi'][:2],1.0]
    direction=calib['rt_inv'][:3,:3] @ np.linalg.solve(calib['nK'],pixel)
    return calib['rt_inv'][:3,3], direction/np.linalg.norm(direction)


def intersect_plane(uv, calib, z):
    origin,direction=ray(uv,calib)
    if abs(direction[2])<1e-10: raise ValueError('Raio paralelo ao plano')
    t=(z-origin[2])/direction[2]
    if t<=0: raise ValueError('Interseção atrás da câmera')
    return origin+t*direction


def project(point, calib):
    p=calib['nK'] @ calib['rt'][:3] @ np.r_[point,1]
    if p[2]<=0: raise ValueError('Ponto atrás da câmera')
    return p[:2]/p[2]-calib['roi'][:2]


def triangulate(observations, calibrations):
    matrices=[]; vectors=[]
    for key,uv in observations.items():
        origin,direction=ray(uv,calibrations[int(key)])
        orthogonal=np.eye(3)-np.outer(direction,direction)
        matrices.append(orthogonal);vectors.append(orthogonal@origin)
    if len(matrices)<2: raise ValueError('Triangulação exige pelo menos duas vistas')
    return np.linalg.lstsq(np.concatenate(matrices),np.concatenate(vectors),rcond=None)[0]


def object_point(spec, local):
    x,y,z=np.deg2rad(spec['rotation_deg'])
    rx=np.array([[1,0,0],[0,np.cos(x),-np.sin(x)],[0,np.sin(x),np.cos(x)]])
    ry=np.array([[np.cos(y),0,np.sin(y)],[0,1,0],[-np.sin(y),0,np.cos(y)]])
    rz=np.array([[np.cos(z),-np.sin(z),0],[np.sin(z),np.cos(z),0],[0,0,1]])
    return np.asarray(spec['position'])+rz@ry@rx@local


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--captura',type=Path,default=ROOT/'saida/imagens_reais/20261014_141328')
    parser.add_argument('--saida',type=Path,default=ROOT/'saida/validacao/geometria')
    parser.add_argument('--planos',action='store_true',help='Gerar projeções sobre Z=0 e Z=0,75 m')
    parser.add_argument('--mesas',action='store_true',help='Projetar tampos norte/oeste nas referências 3 e 4')
    args=parser.parse_args(); args.saida.mkdir(parents=True,exist_ok=True)
    calibs=load_calibrations()
    data=json.loads((ROOT/'scene_data/landmarks.json').read_text())
    specs={o['id']:o for o in json.loads((ROOT/'scene_data/objects.json').read_text())['objects']}
    images={i:cv2.imread(str(args.captura/f'corrigidas_roi/camera_{i}.png')) for i in range(1,5)}
    if any(im is None for im in images.values()): raise FileNotFoundError(args.captura)
    result={'pixel_space':'undistorted_roi','manual_annotation_uncertainty_px':data['annotations_uncertainty_px'],
            'warning':'Ajuste e holdout cobrem somente dois cantos da mesa L. Não validam toda a sala.',
            'fit':[],'holdout':[]}
    for group,key in [('fit','fit_landmarks'),('holdout','holdout_landmarks')]:
        for lm in data[key]:
            world=object_point(specs[lm['object_id']],lm['local_position'])
            row={'id':lm['id'],'model_world':world.tolist(),'observations':{}}
            if group=='fit': row['triangulated_world']=triangulate(lm['observations'],calibs).tolist()
            for cam,uv in lm['observations'].items():
                i=int(cam);pred=project(world,calibs[i]);err=float(np.linalg.norm(pred-uv))
                row['observations'][cam]={'manual_roi':uv,'projected_roi':pred.tolist(),'error_px':err}
                obs=tuple(map(int,uv));pp=tuple(np.rint(pred).astype(int))
                cv2.circle(images[i],obs,6,(0,255,0),1)
                cv2.drawMarker(images[i],pp,(0,0,255),cv2.MARKER_CROSS,11,1)
                cv2.line(images[i],obs,pp,(0,220,255),1)
                cv2.putText(images[i],lm['id'],(pp[0]+6,pp[1]-8),0,.35,(20,20,240),1)
            result[group].append(row)
    for i,im in images.items():cv2.imwrite(str(args.saida/f'landmarks_camera_{i}.png'),im)
    for key in ('fit','holdout'):
        errors=[o['error_px'] for lm in result[key] for o in lm['observations'].values()]
        result[key+'_rmse_px']=float(np.sqrt(np.mean(np.square(errors))))
    (args.saida/'reprojection.json').write_text(json.dumps(result,indent=2)+'\n')
    if args.mesas:
        for i in (3,4):
            img=cv2.imread(str(args.captura/f'corrigidas_roi/camera_{i}.png'))
            for name,spec in specs.items():
                if not name.startswith(('Desk_North','Desk_West')):continue
                w,d,h=spec['dimensions']
                corners=[[-w/2,-d/2,h],[w/2,-d/2,h],[w/2,d/2,h],[-w/2,d/2,h]]
                pixels=np.rint([project(object_point(spec,np.array(v)),calibs[i]) for v in corners]).astype(np.int32)
                color=(0,170,255) if name.startswith('Desk_North') else (255,180,0)
                cv2.polylines(img,[pixels],True,color,1,cv2.LINE_AA)
            cv2.imwrite(str(args.saida/f'mesas_camera_{i}.png'),img)
    if args.planos:
        X,Y=np.meshgrid(np.linspace(-3.475,3.475,695),np.linspace(4.335,-4.335,867))
        for z in (0,.75):
            for i,c in calibs.items():
                img=cv2.imread(str(args.captura/f'corrigidas_roi/camera_{i}.png'))
                K=c['nK'].copy();K[:2,2]-=c['roi'][:2]
                xyz=np.stack((X,Y,np.full_like(X,z),np.ones_like(X)),axis=-1)
                p=xyz@(K@c['rt'][:3]).T
                u=(p[:,:,0]/p[:,:,2]).astype('float32');v=(p[:,:,1]/p[:,:,2]).astype('float32')
                warp=cv2.remap(img,u,v,cv2.INTER_LINEAR,borderValue=(30,30,30));warp[p[:,:,2]<=0]=30
                cv2.imwrite(str(args.saida/f'plano_z{z}_camera_{i}.png'),warp)
    print(json.dumps({k:v for k,v in result.items() if k.endswith('_rmse_px')},indent=2))


if __name__=='__main__':main()
