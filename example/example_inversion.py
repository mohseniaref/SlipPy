#!/usr/bin/env python
import numpy as np
import cosinv.patch
import cosinv.basis
import cosinv.io
from cosinv.gbuild import flatten_vector_array
from cosinv.gbuild import build_system_matrix
import matplotlib.pyplot as plt
import scipy.optimize
from mpl_toolkits.basemap import Basemap
np.random.seed(1)

def geodetic_to_cartesian(pos_geo,basemap):
  pos_geo = np.asarray(pos_geo)
  pos_x,pos_y = bm(pos_geo[:,0],pos_geo[:,1])
  pos_cart = np.array([pos_x,pos_y]).T
  return pos_cart

def cartesian_to_geodetic(pos_cart,basemap):
  pos_cart = np.asarray(pos_cart)
  pos_lon,pos_lat = bm(pos_cart[:,0],pos_cart[:,1],inverse=True)
  pos_geo = np.array([pos_lon,pos_lat]).T
  return pos_geo

def create_default_basemap(lon_lst,lat_lst,resolution='c'):
  ''' 
  creates a basemap that bounds lat_lst and lon_lst
  '''
  lon_buff = (max(lon_lst) - min(lon_lst))/20.0
  lat_buff = (max(lat_lst) - min(lat_lst))/20.0
  if lon_buff < 0.2:
    lon_buff = 0.2

  if lat_buff < 0.2:
    lat_buff = 0.2

  llcrnrlon = min(lon_lst) - lon_buff
  llcrnrlat = min(lat_lst) - lat_buff
  urcrnrlon = max(lon_lst) + lon_buff
  urcrnrlat = max(lat_lst) + lat_buff
  lon_0 = (llcrnrlon + urcrnrlon)/2.0
  lat_0 = (llcrnrlat + urcrnrlat)/2.0
  return Basemap(projection='tmerc',
                 lon_0 = lon_0,
                 lat_0 = lat_0,
                 llcrnrlon = llcrnrlon,
                 llcrnrlat = llcrnrlat,
                 urcrnrlon = urcrnrlon,
                 urcrnrlat = urcrnrlat,
                 resolution = resolution)

def reg_nnls(G,L,d):
  dext = np.concatenate((d,np.zeros(L.shape[0])))
  Gext = np.vstack((G,L))
  return scipy.optimize.nnls(Gext,dext)[0]


### patch specifications
#####################################################################
#####################################################################
#####################################################################
strike = 20.0 # degrees
dip = 80.0 # degrees
length = 1000000.0
width = 1000000.0
segment_pos_geo = np.array([0.0,0.0,0.0]) # top center of segment
Nl = 40
Nw = 20
slip_basis = np.array([[ 1.0,  1.0, 0.0],
                       [ 1.0, -1.0, 0.0]])

#####################################################################
#####################################################################
#####################################################################

## observation points
#####################################################################
pos_geo,disp,sigma = cosinv.io.read_gps_data('synthetic_gps.txt')
Nx  = len(pos_geo)

# create basemap to convert geodetic to cartesian
bm = create_default_basemap(pos_geo[:,0],pos_geo[:,1])
pos_cart = geodetic_to_cartesian(pos_geo,bm)
pos_cart = np.hstack((pos_cart,np.zeros((Nx,1))))

# flatten the positions, displacements, and uncertainties
pos_f = pos_cart[:,None,:].repeat(3,axis=1).reshape((Nx*3,3))
disp_f = disp.reshape(Nx*3)
sigma_f = sigma.reshape(Nx*3)

# get the basis vector for each displacement component
disp_basis = cosinv.basis.cardinal_basis((Nx,3))
disp_basis_f = disp_basis.reshape((Nx*3,3))


### build patches
#####################################################################
segment_pos_cart = geodetic_to_cartesian([segment_pos_geo[:2]],bm)[0]
segment_pos_cart = np.hstack((segment_pos_cart,segment_pos_geo[2]))

P = cosinv.patch.Patch(segment_pos_cart,length,width,strike,dip)
Ps = np.array(P.discretize(Nl,Nw))
Ns = len(Ps)
Ds = len(slip_basis)
slip_basis = np.array([slip_basis for i in Ps])
slip_basis_f = slip_basis.reshape((Ns*Ds,3))
Ps_f = Ps[:,None].repeat(Ds,axis=1).reshape((Ns*Ds,)) 


#####################################################################
### Build System matrix
#####################################################################
G = cosinv.gbuild.build_system_matrix(pos_f,Ps_f,disp_basis_f,slip_basis_f)
L = 0.001*np.eye(len(Ps_f))

#####################################################################
### Estimate slip
#####################################################################
slip_f = reg_nnls(G,L,disp_f)
pred_f = G.dot(slip_f)

slip = slip_f.reshape((Ns,Ds))
slip = cosinv.basis.cardinal_components(slip,slip_basis)
pred = pred_f.reshape((Nx,3))
pred_sigma = np.zeros((Nx,3))


#####################################################################
### write solution
#####################################################################
cosinv.io.write_gps_data(pos_geo,pred,pred_sigma,'predicted_gps.txt')

patch_pos_cart = np.array([i.patch_to_user([0.0,1.0,0.0])[:2] for i in Ps])
patch_pos_geo = cartesian_to_geodetic(patch_pos_cart,bm)
patch_depth = np.array([i.patch_to_user([0.0,1.0,0.0])[2] for i in Ps])
patch_strike = [i.strike for i in Ps]
patch_dip = [i.dip for i in Ps]
patch_length = [i.length for i in Ps]
patch_width = [i.width for i in Ps]

cosinv.io.write_slip_data(patch_pos_geo,patch_depth,
                          patch_strike,patch_dip,
                          patch_length,patch_width,
                          slip,'predicted_slip.txt')

#####################################################################
### Plot Solution
#####################################################################
input = cosinv.io.read_slip_data('predicted_slip.txt')

pred_pos_geo,pred_disp,pred_sigma = cosinv.io.read_gps_data('predicted_gps.txt')
Nx = len(pred_pos_geo)
bm = create_default_basemap(pred_pos_geo[:,0],pred_pos_geo[:,1])
pred_pos_cart = geodetic_to_cartesian(pred_pos_geo,bm)

obs_pos_geo,obs_disp,obs_sigma = cosinv.io.read_gps_data('synthetic_gps.txt')
obs_pos_cart = geodetic_to_cartesian(obs_pos_geo,bm)

patch_pos_geo = input[0]
patch_depth = input[1]
patch_pos_cart = geodetic_to_cartesian(patch_pos_geo,bm)
patch_pos_cart = np.hstack((patch_pos_cart,patch_depth[:,None]))
patch_strike = input[2]
patch_dip = input[3]
patch_length = input[4]
patch_width = input[5]
slip = input[6]
Ps = [cosinv.patch.Patch(p,l,w,s,d) for p,l,w,s,d in zip(patch_pos_cart,
                                                         patch_length,
                                                         patch_width,
                                                         patch_strike,
                                                         patch_dip)]
fig,ax = plt.subplots()
ax.set_title('left lateral')
bm.drawcoastlines(ax=ax)
q = ax.quiver(obs_pos_cart[:,0],obs_pos_cart[:,1],
              obs_disp[:,0],obs_disp[:,1],
              zorder=1,color='k',scale=1.0)
ax.quiver(pred_pos_cart[:,0],pred_pos_cart[:,1],
          pred_disp[:,0],pred_disp[:,1],
          zorder=1,color='m',scale=1.0)
          
ax.quiverkey(q,0.8,0.2,0.05,'0.05 m')
ps = cosinv.patch.draw_patches(Ps,colors=slip[:,0],ax=ax,edgecolor='none',zorder=0)
fig.colorbar(ps,ax=ax)
fig,ax = plt.subplots()

ax.set_title('thrust')
bm.drawcoastlines(ax=ax)
q = ax.quiver(obs_pos_cart[:,0],obs_pos_cart[:,1],
              obs_disp[:,0],obs_disp[:,1],
              zorder=1,color='k',scale=1.0)
ax.quiver(pred_pos_cart[:,0],pred_pos_cart[:,1],
          pred_disp[:,0],pred_disp[:,1],
          zorder=1,color='m',scale=1.0)
          
ax.quiverkey(q,0.8,0.2,0.05,'0.05 m')
ps = cosinv.patch.draw_patches(Ps,colors=slip[:,1],ax=ax,edgecolor='none',zorder=0)
fig.colorbar(ps,ax=ax)
plt.show()
quit()